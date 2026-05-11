from discord import Activity, ActivityType, ActivityButton
from config import DEFAULT_COVER
from fuzzywuzzy import fuzz

PITCH_CLASSES = {-1: '?', 0: 'C', 1: 'C♯ / D♭', 2: 'D', 3: 'D♯ / E♭', 4: 'E', 5: 'F', 6: 'F♯ / G♭', 7: 'G', 8: 'G♯ / A♭', 9: 'A', 10: 'A♯ / B♭', 11: 'B'} #idk where do i put it, let it be here

def build_activity(track:dict, current_line:str, lyrics:list, ts_payload:dict, return_basic:bool = False) -> Activity:
	title, artist, album, isrc, duration, provider, urls, stats = track.values()
	base = {
		'type': ActivityType.listening,
		'application_id': 1295028329069674609,
		'name': f'{title} by {artist}',
		'details': title[:128],
		'details_url': urls.get('track_url', None), 
		'state': f'by {artist}'[:128],
		'state_url': urls.get('artist_url', None),
		'timestamps': ts_payload,
		'assets': {
			'large_image': f"mp:external/{urls.get('proxified_cover_url', '') or DEFAULT_COVER}",
			'large_text': f'on {album}'[:128] if album else None,
			'large_url': urls.get('album_url', None),
		},
		'buttons': [ActivityButton('This RPC is open-source!', 'https://github.com/kowalskyy/syncedlyrics-userbot')],
	}

	if lyrics and not return_basic:
		base['details'] = f'🎤 {current_line}'[:128]
		base['details_url'] = urls.get('album_url', None)
		base['state'] = title[:128]
		base['state_url'] = urls.get('track_url', None)
		base['assets']['large_text'] = f'by {artist}'[:128]
		base['assets']['large_url'] = urls.get('artist_url', None)
	
	if stats and (small_image := urls.get('proxified_small_image', '')):
		base['assets']['small_image'] = f'mp:external/{small_image}'
		base['assets']['small_text'] = f'BPM: {int(stats["tempo"])}\nKey: {PITCH_CLASSES.get(stats["key"])} {"Major" if stats["mode"] == 1 else "Minor"}'

	return Activity(**base)

def build_track_info(data:dict, service:str, artist:str, title:str) -> dict:
	def walk(data, path):
		for k in path: data = data[k] if isinstance(data, list) else data.get(k, {})
		return data
	base = {
		'title': title,
		'artist': artist,
		'album': '',
		'isrc': '',
		'duration': 0,
		'provider': '',
		'urls': {},
		'statistics': {}
	}
	match service.lower():
		case 'deezer':
			keys = {
				'title': ['data', 0, 'title'],
				'artist': ['data', 0, 'artist', 'name'],
				'album': ['data', 0, 'album', 'title'],
				'isrc': ['data', 0, 'isrc'],
				'duration': ['data', 0, 'duration'],
				'urls': {
					'track_url': ['data', 0, 'link'],
					'album_url': ['data', 0, 'album', 'id'],
					'artist_url': ['data', 0, 'artist', 'link'],
					'cover_url': ['data', 0, 'album', 'cover_xl']
				}
			}
		case 'apple.music':
			keys = {
				'title': ['results', 0, 'trackName'],
				'artist': ['results', 0, 'artistName'],
				'album': ['results', 0, 'collectionName'],
				'duration': ['results', 0, 'trackTimeMillis'],
				'urls': {
					'track_url': ['results', 0, 'trackViewUrl'],
					'album_url': ['results', 0, 'collectionViewUrl'],
					'artist_url': ['results', 0, 'artistViewUrl'],
					'cover_url': ['results', 0, 'artworkUrl100']
				}
			}
		case _: return base

	if not fuzz.token_sort_ratio(f"{walk(data, keys['artist'])} {walk(data, keys['title'])}", f'{artist} {title}') >= 60: return base

	for key, path in keys.items():
		if isinstance(path, list): base[key] = walk(data, path)
		elif isinstance(path, dict):
			for dict_key, dict_path in path.items(): base[key][dict_key] = walk(data, dict_path)

	if service.lower() == 'deezer': base['urls']['album_url'] = f"https://www.deezer.com/album/{base['urls']['album_url']}"; base['provider'] = 'deezer'
	if service.lower() == 'apple.music': 
		base['duration'] /= 1000
		base['urls']['track_url'] = base['urls']['track_url'].split('?')[0]
		base['urls']['cover_url'] = base['urls']['cover_url'].replace('100x100', '1000x1000')
		base['provider'] = 'apple.music'

	return base
