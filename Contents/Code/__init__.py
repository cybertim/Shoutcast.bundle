RE_FILE = Regex('File1=(https?://.+)')

SC_DEVID         = 'sh1t7hyn3Kh0jhlV'
SC_ROOT          = 'http://api.shoutcast.com/'
SC_SEARCH        = SC_ROOT + 'legacy/stationsearch?k=' + SC_DEVID + '&search=%s'
SC_BYGENRE       = SC_ROOT + 'legacy/genresearch?k=' + SC_DEVID + '&genre=%s'
SC_NOWPLAYING    = SC_ROOT + 'station/nowplaying?k=' + SC_DEVID + '&ct=%s&f=xml'
SC_TOP500        = SC_ROOT + 'legacy/Top500?%sk=' + SC_DEVID
SC_ALLGENRES     = SC_ROOT + 'legacy/genrelist?k=' + SC_DEVID
SC_PRIMARYGENRES = SC_ROOT + 'genre/primary?k=' + SC_DEVID + '&f=xml'
SC_SUBGENRES     = SC_ROOT + 'genre/secondary?parentid=%s&k=' + SC_DEVID + '&f=xml'
SC_PLAY          = 'http://yp.shoutcast.com/sbin/tunein-station.pls?id=%s&k='+ SC_DEVID
SC_ICON_ADD_FAVORITE = 'add_favorite.png'
SC_ICON_DEL_FAVORITE = 'del_favorite.png'

####################################################################################################
def Start():

	ObjectContainer.title1 = "SHOUTcast"
	HTTP.CacheTime = 3600*5

####################################################################################################
def CreateDict():

	# Create dict objects
	Dict['genres'] = {}
	Dict['sortedGenres'] = []
	Dict['favorites'] = []

####################################################################################################
def UpdateCache():

	genres = {}

	for g in XML.ElementFromURL(SC_PRIMARYGENRES).xpath("//genre"):
		genre = g.get('name')
		subgenres = []

		if g.get('haschildren') == 'true':
			for sg in XML.ElementFromURL(SC_SUBGENRES % g.get('id')).xpath("//genre"):
				subgenres.append(sg.get('name'))

		genres[genre] = subgenres

	Dict['genres'] = genres
	Dict['sortedGenres'] = sorted(genres.keys())

####################################################################################################
@handler("/music/shoutcast", "SHOUTcast")
def MainMenu():

	oc = ObjectContainer()
	oc.add(DirectoryObject(key=Callback(Favorites), title="Favorites"))
	oc.add(DirectoryObject(key=Callback(GetGenres), title=L('By Genre')))
	oc.add(InputDirectoryObject(key=Callback(GetGenre, title="", queryParamName=SC_SEARCH), title=L("Search for Stations by Keyword..."), prompt=L("Search for Stations")))
	oc.add(InputDirectoryObject(key=Callback(GetGenre, title="Now Playing", queryParamName=SC_NOWPLAYING), title=L("Search for Now Playing by Keyword..."), prompt=L("Search for Now Playing")))
	oc.add(DirectoryObject(key=Callback(GetGenre, title=L("Top 500 Stations"), queryParamName=SC_TOP500, query='**ignore**'), title=L("Top 500 Stations")))
	oc.add(PrefsObject(title=L("Preferences...")))

	return oc

####################################################################################################
@route("/music/shoutcast/genres")
def GetGenres():

	if Dict['sortedGenres'] == None:
		UpdateCache()

	oc = ObjectContainer(title2=L('By Genre'))
	sortedGenres = Dict['sortedGenres']

	for genre in sortedGenres:
		oc.add(DirectoryObject(
			key = Callback(GetSubGenres, genre=genre),
			title = genre
		))

	return oc

####################################################################################################
@route("/music/shoutcast/subgenres")
def GetSubGenres(genre):

	oc = ObjectContainer(title2=genre)
	oc.add(DirectoryObject(
		key = Callback(GetGenre, title=genre, query=genre),
		title = "All %s Stations" % genre
	))

	genres = Dict['genres']

	for subgenre in genres[genre]:
		if XML.ElementFromURL(SC_BYGENRE % String.Quote(subgenre, usePlus=True)).xpath('//station') != []: #skip empty subgenres
			oc.add(DirectoryObject(
				key = Callback(GetGenre, title=subgenre),
				title = subgenre
			))

	return oc

####################################################################################################
@route("/music/shoutcast/genre")
def GetGenre(title, queryParamName=SC_BYGENRE, query=''):

	if title == '' and query != '' and query != '**ignore**':
		title = query

	oc = ObjectContainer(title1='By Genre', title2=title)

	if query == '':
		query = title
	elif query == '**ignore**':
		query = ''
	else:
		if len(query) < 3 and queryParamName == SC_SEARCH: #search doesn't work for short strings
			return ObjectContainer(header='Search error.', message='Searches must have a minimum of three characters.')

		oc.title1 = 'Search'
		oc.title2 = '"' + query + '"'

	fullUrl = queryParamName % String.Quote(query, usePlus=True)
	xml = XML.ElementFromURL(fullUrl, cacheTime=1)
	root = xml.xpath('//tunein')[0].get('base')

	min_bitrate = Prefs['min-bitrate']
	if min_bitrate[0] == '(':
		min_bitrate = 0
	else:
		min_bitrate = int(min_bitrate.split()[0])

	stations = xml.xpath('//station')

	# Sort.
	if Prefs['sort-key'] == 'Bitrate':
		stations.sort(key = lambda station: station.get('br'), reverse=True)
	elif Prefs['sort-key'] == 'Listeners':
		stations.sort(key = lambda station: station.get('lc'), reverse=True)
	else:
		stations.sort(key = lambda station: station.get('name'), reverse=False)

	for station in stations:
		listeners = 0
		bitrate = int(station.get('br'))

		url = SC_PLAY % station.get('id')
		title = station.get('name').split(' - a SHOUTcast.com member station')[0]
		summary = station.get('ct')

		if station.get('mt') == "audio/mpeg":
			fmt = 'mp3'
		elif station.get('mt') == "audio/aacp":
			fmt = 'aac'
		else:
			continue

		if station.get('lc'):
			if len(summary) > 0:
				summary += "\n"

			listeners = int(station.get('lc'))

			if listeners > 0:
				summary += station.get('lc') + ' Listeners'

		# Filter.
		if bitrate >= min_bitrate:
			oc.add(DirectoryObject(
				key = Callback(CreateTrackMenu, sub_title=title, url=url, title=title, summary=summary, fmt=fmt),
				title = title,
				summary = summary,		
			))

	return oc

####################################################################################################
@route("/music/shoutcast/track")
def CreateTrackMenu(sub_title, url, title, summary, fmt):

	if fmt == 'mp3':
		container = Container.MP3
		audio_codec = AudioCodec.MP3
	elif fmt == 'aac':
		container = Container.MP4
		audio_codec = AudioCodec.AAC


	track_object = TrackObject(
		key = Callback(CreateTrackMenu, sub_title=sub_title, url=url, title=title, summary=summary, fmt=fmt),
		rating_key = url,
		title = 'Start Playback',
		summary = summary,
		items = [
			MediaObject(
				parts = [
					PartObject(key=Callback(PlayAudio, url=url, ext=fmt))
				],
				container = container,
				audio_codec = audio_codec,
				bitrate = 192,
				audio_channels = 2
			)
		]
	)
	
	favorite_object = DirectoryObject(
		key = Callback(AddFavorite, url=url, title=title, summary=summary, fmt=fmt),
		title = "Add Favorites",
		summary = "You can add " + title + " to your Favorites.",
		thumb = R(SC_ICON_ADD_FAVORITE)
	)
	favorites = Dict['favorites']
	for favorite in favorites:
		if favorite['url'] == url:
			favorite_object = DirectoryObject(
				key = Callback(DelFavorite, url=url, title=title),
				title = "Remove Favorites",
				summary = "You can remove " + title + " from your Favorites.",
				thumb = R(SC_ICON_DEL_FAVORITE)
			)

	oc = ObjectContainer(title1=sub_title, title2=title, replace_parent=True, no_cache=True)
	oc.add(track_object)
	oc.add(favorite_object)
	return oc

####################################################################################################
def PlayAudio(url):

	content = HTTP.Request(url, cacheTime=0).content
	file_url = RE_FILE.search(content)

	if file_url:
		stream_url = file_url.group(1)
		if stream_url[-1] == '/':
			stream_url += ';'
		else:
			stream_url += '/;'
		return Redirect(stream_url)
	else:
		raise Ex.MediaNotAvailable

####################################################################################################
def GetFavorites(oc):

	if Dict['favorites'] == None:
		Dict['favorites'] = []

	#oc = ObjectContainer(title1='Favorites', no_cache=True)
	favorites = Dict['favorites']

	for favorite in favorites:
		oc.add(DirectoryObject(
			key = Callback(CreateTrackMenu, sub_title='Favorites', url=favorite['url'], title=favorite['title'], summary=favorite['summary'], fmt=favorite['fmt']),
			title = favorite['title'],
			summary = favorite['summary'],		
		))		

	return oc


#####################################################################################
# Favorites
#####################################################################################
@route('/music/shoutcast/favorites')
def Favorites():

	oc = ObjectContainer(title1='Favorites')
	return GetFavorites(oc)

#####################################################################################
# Add Favorite
##################################################################################### 
@route('/music/shoutcast/addfavorite')
def AddFavorite(url, title, summary, fmt):
	
	oc = ObjectContainer(title1='Favorites', header=title, message='The station has been added to your favorites.')

	if Dict['favorites'] == None:
		Dict['favorites'] = []

	favorite = {}
	favorite['title'] = title
	favorite['url'] = url
	favorite['summary'] = summary
	favorite['fmt'] = fmt

	Dict['favorites'].append(favorite)

	Dict.Save()

	return GetFavorites(oc)

#####################################################################################
# Add Favorite
##################################################################################### 
@route('/music/shoutcast/delfavorite')
def DelFavorite(url, title):

	oc = ObjectContainer(title1='Favorites', header=title, message='The station has been removed from your favorites.')

	if Dict['favorites'] == None:
		Dict['favorites'] = []

	favorites = Dict['favorites']

	fav_item = None
	for favorite in favorites:
		if favorite['url'] == url:
			fav_item = favorite

	if fav_item != None:
		Dict['favorites'].remove(fav_item)

	Dict.Save()

	return GetFavorites(oc)
