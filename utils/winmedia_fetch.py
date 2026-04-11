from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as mc
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSession as ms
# from winrt.windows.storage.streams import DataReader
from logging import getLogger

logger = getLogger('winmedia_fetch')

async def get_media_info() -> dict:
	try:
		sessions = await mc.request_async()
		current_session = sessions.get_current_session()
		if not current_session: logger.debug('no media sessions'); return {}
		
		props = await current_session.try_get_media_properties_async()
		if not props: return {}
		timeline = current_session.get_timeline_properties()
		status = current_session.get_playback_info().playback_status
		
		pos = timeline.position.total_seconds()
		dur = timeline.end_time.total_seconds()

		return {
			'title': props.title,
			'artist': props.artist,
			'status': status,
			'position': pos,
			'duration': dur
			# '_session': current_session
		}
	except Exception as e: logger.error(e); return {}

# async def get_media_cover(session: ms) -> bytes | None:
# 	if not session: return None

# 	props = await session.try_get_media_properties_async()
# 	if not props or not props.thumbnail: return None

# 	cover = await props.thumbnail.open_read_async()
# 	reader = DataReader(cover)
# 	await reader.load_async(cover.size)

# 	buffer = bytearray(cover.size)
# 	reader.read_bytes(buffer)
# 	return bytes(buffer)
