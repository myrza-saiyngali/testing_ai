# import logging
# import requests
# from tempfile import TemporaryFile
# from urllib.request import urlopen
# from django.conf import settings
# from django.core.files import File
# from django.utils import timezone
# from main.models import (
#     VideoAvatar,
#     VideoAvatarTemplate,
# )
# from jlab.models import (
#     MessageObject,
#     MessageObjectStatuses,
#     MessageObjectTypes,
#     TaskMessage,
# )
# # from account.models import UserOnboarding
# from main.utils import generate_image
# from main.api import StreamAgentAPI
# from ai.celery import app

# DUMMY_IMAGE_URL = "https://d7pqxnw01lpes.cloudfront.net/media/jlab_examples/example_4.webp"
# DUMMY_VIDEO_URL = "https://d7pqxnw01lpes.cloudfront.net/media/jlab/avatars/video/video_310.mp4"
# SYNERGIZER_STRENGTH = 1
# if settings.DEBUG:
#     WEBHOOK_URL = "https://stage.api.jobescape.me/ai_v2/synclab/"
# else:
#     WEBHOOK_URL = "https://api.jobescape.me/ai_v2/synclab/"


# @app.task(ignore_result=True)
# def dummy_generate_video_task(msg_obj_id: int) -> bool:
#     try:
#         ai_msg_obj = MessageObject.objects.get(id=msg_obj_id)
#     except:  # pylint: disable=W0702
#         return False
#     with TemporaryFile("w+b") as tmp_file:
#         with urlopen(DUMMY_VIDEO_URL) as response:
#             tmp_file.write(response.read())
#         filename = f"stage_video_{ai_msg_obj.pk}.mp4" if settings.DEBUG else f"video_{ai_msg_obj.pk}.mp4"
#         ai_msg_obj.file.save(filename, File(tmp_file), save=False)
#     ai_msg_obj.status = MessageObjectStatuses.VIDEO_READY
#     ai_msg_obj.save()
#     return True


# @app.task(ignore_result=True)
# def dummy_generate_image_task(msg_obj_id: int) -> bool:
#     try:
#         ai_msg_obj = MessageObject.objects.get(id=msg_obj_id)
#     except:  # pylint: disable=W0702
#         return False
#     with TemporaryFile("w+b") as tmp_file:
#         with urlopen(DUMMY_IMAGE_URL) as response:
#             tmp_file.write(response.read())
#         filename = f"stage_image_{ai_msg_obj.pk}.webp" if settings.DEBUG else f"image_{ai_msg_obj.pk}.webp"
#         ai_msg_obj.file.save(filename, File(tmp_file), save=False)
#     ai_msg_obj.status = MessageObjectStatuses.IMAGE_READY
#     ai_msg_obj.save()
#     return True


# @app.task(ignore_result=True)
# def generate_video_task(user_msg_id: int, msg_obj_id: int, avatar_id: int, retry=True) -> bool:
#     """
#     The task uses Elevenlabs to generate audio track for the provided TaskMessage's text content.
#     Then both VideoAvatar template and the audio track are sent to Synclab for lib-syncing.
#     Synclab uses a webhook to send generated video back to our backend.

#     :param user_msg_id: User's TaskMessage ID
#     :type user_msg_id: int
#     :param msg_obj_id: Agent's (AI's) response MessageObject ID
#     :type msg_obj_id: int
#     :param avatar_id: VideoAvatar ID
#     :type avatar_id: int
#     :param retry: Whether a retry is allowed or not, defaults to True
#     :type retry: bool, optional
#     :return: Whether requesting audio and video was successful or not
#     :rtype: bool
#     """
#     exc_msg = "Generate video task: Aborting because "
#     error = False
#     # Fetch instances
#     try:
#         ai_msg_obj = MessageObject.objects.get(id=msg_obj_id)
#         user_message = TaskMessage.objects.get(id=user_msg_id)
#         avatar = VideoAvatar.objects.get(id=avatar_id)
#         avatar_template = VideoAvatarTemplate.objects.filter(
#             avatar=avatar).first()
#         if not avatar_template:
#             logging.warning(
#                 "%s VideoAvatarTemplate does not exist! id=%d", exc_msg, msg_obj_id)
#             error = True
#         # Fetch text content from user's TaskMessage
#         contents = user_message.objs.filter(content_type=MessageObjectTypes.TEXT).values_list(
#             "content", flat=True)  # type: ignore
#         if not contents or not any(contents):
#             logging.warning(
#                 "%s user's TaskMessage does not contain non-empty text objects! user_msg_id=%d", exc_msg, user_msg_id)
#             error = True
#     except MessageObject.DoesNotExist:
#         logging.warning(
#             "%s related MessageObject does not exist! id=%d", exc_msg, msg_obj_id)
#         error = True
#     except TaskMessage.DoesNotExist:
#         logging.warning(
#             "%s user's TaskMessage does not exist! id=%d", exc_msg, user_msg_id)
#         error = True
#     except VideoAvatar.DoesNotExist:
#         logging.error("%s VideoAvatar does not exist! id=%d",
#                       exc_msg,  avatar_id)
#         error = True
#     if error:
#         MessageObject.objects.filter(id=msg_obj_id).update(
#             status=MessageObjectStatuses.ERROR)
#         return False
#     # Skip if audio had already been generated previously (presume this is a retry)
#     if not ai_msg_obj.file:
#         # Set status to ACCEPTED
#         MessageObject.objects.filter(id=msg_obj_id).update(
#             status=MessageObjectStatuses.ACCEPTED)
#         # Assemble the text
#         text = "\n".join([i for i in contents if i])
#         # Request Audio
#         url = f"https://api.elevenlabs.io/v1/text-to-speech/{avatar.el_id}"
#         payload = {
#             "text": text,
#             "model_id": "eleven_monolingual_v1",
#             "voice_settings": {
#                 "stability": avatar.stability,
#                 "similarity_boost": avatar.similarity_boost,
#                 "style": avatar.style,
#                 "use_speaker_boost": avatar.use_speaker_boost,
#             },
#         }
#         headers = {"Content-Type": "application/json",
#                    "xi-api-key": settings.ELEVENLABS_KEY}
#         response: requests.Response = requests.request(
#             "POST", url, json=payload, headers=headers, timeout=settings.REQUESTS_TIMEOUT, stream=True)
#         if response.status_code != 200:
#             logging.warning("%s ElevenLabs returned status_code=%s",
#                             exc_msg, str(response.status_code))
#             # Retry on fail if allowed
#             if retry:
#                 logging.info(
#                     "Generate video task: Scheduling retry task. msg_obj_id=%d", msg_obj_id)
#                 generate_video_task.apply_async(
#                     args=[user_msg_id, msg_obj_id, avatar_id, False],
#                     eta=timezone.now() + timezone.timedelta(minutes=1)
#                 )
#                 MessageObject.objects.filter(id=msg_obj_id).update(
#                     status=MessageObjectStatuses.RETRY)
#             else:
#                 MessageObject.objects.filter(id=msg_obj_id).update(
#                     status=MessageObjectStatuses.ERROR)
#             return False
#         # Save response audio to message object file
#         filename = f"stage_audio_{msg_obj_id}.mp3" if settings.DEBUG else f"audio_{msg_obj_id}.mp3"
#         tmp_file = TemporaryFile("w+b")
#         for chunk in response.iter_content(1024):
#             tmp_file.write(chunk)  # type: ignore
#         ai_msg_obj.file.save(filename, File(tmp_file), save=False)
#         ai_msg_obj.status = MessageObjectStatuses.AUDIO_READY
#         ai_msg_obj.save()
#         tmp_file.close()

#     # Request Video
#     url = "https://api.synclabs.so/lipsync"
#     payload = {
#         "audioUrl": ai_msg_obj.file.url,
#         "videoUrl": avatar_template.file.url,  # type: ignore
#         "model": "sync-1.6.0",
#         "synergizerStrength": SYNERGIZER_STRENGTH,
#         "webhookUrl": WEBHOOK_URL
#     }
#     headers = {"x-api-key": settings.SYNCLAB_KEY,
#                "Content-Type": "application/json"}
#     response: requests.Response = requests.request(
#         "POST", url, json=payload, headers=headers, timeout=settings.REQUESTS_TIMEOUT)
#     if response.status_code != 201:
#         logging.warning("%s SyncLab returned status_code=%s",
#                         exc_msg, str(response.status_code))
#         # Retry on fail if allowed
#         if retry:
#             logging.info(
#                 "Generate video task: Scheduling retry task. msg_obj_id=%d", msg_obj_id)
#             generate_video_task.apply_async(
#                 args=[user_msg_id, msg_obj_id, avatar_id, False],
#                 eta=timezone.now() + timezone.timedelta(minutes=1)
#             )
#             MessageObject.objects.filter(id=msg_obj_id).update(
#                 status=MessageObjectStatuses.RETRY)
#         else:
#             MessageObject.objects.filter(id=msg_obj_id).update(
#                 status=MessageObjectStatuses.ERROR)
#         return False
#     # Update status and video id
#     data = response.json()
#     ai_msg_obj.video_id = data["id"]
#     ai_msg_obj.status = MessageObjectStatuses.AWAITING
#     ai_msg_obj.save()
#     return True


# @app.task(ignore_result=True)
# def generate_image_task(user_msg_id: int, msg_obj_id: int):
#     exc_msg = "Generate image task: Aborting because "
#     error = True
#     # Fetch instances
#     try:
#         ai_msg_obj = MessageObject.objects.select_related(
#             "message__agent").get(id=msg_obj_id)
#         ai_message = ai_msg_obj.message
#         user_message = TaskMessage.objects.prefetch_related(
#             "objs").get(id=user_msg_id)
#         # Fetch text content from user's TaskMessage
#         prompt = StreamAgentAPI(
#             ai_message).get_message_text_content(user_message)
#         # Check if there's image already
#         if ai_msg_obj.file:
#             logging.warning(
#                 "%s related MessageObject already has a file! id=%d", exc_msg, user_msg_id)
#         else:
#             error = False
#     except MessageObject.DoesNotExist:
#         logging.warning(
#             "%s related MessageObject does not exist! id=%d", exc_msg, msg_obj_id)
#     except TaskMessage.DoesNotExist:
#         logging.warning(
#             "%s user's TaskMessage does not exist! id=%d", exc_msg, user_msg_id)
#     if error:
#         MessageObject.objects.filter(id=msg_obj_id).update(
#             status=MessageObjectStatuses.ERROR)
#         return False
#     # Generate image and save
#     MessageObject.objects.filter(id=msg_obj_id).update(
#         status=MessageObjectStatuses.AWAITING)
#     try:
#         images = generate_image(prompt, 1, "hd")
#         assert images[0].url
#     except Exception as exc:
#         logging.warning(
#             "%s openai failed to generate image! id=%d; exception=%s", exc_msg, user_msg_id, str(exc))
#         MessageObject.objects.filter(id=msg_obj_id).update(
#             status=MessageObjectStatuses.ERROR)
#         return False
#     with TemporaryFile("w+b") as tmp_file:
#         with urlopen(images[0].url) as response:
#             tmp_file.write(response.read())
#         filename = f"stage_image_{ai_msg_obj.pk}.jpeg" if settings.DEBUG else f"image_{ai_msg_obj.pk}.jpeg"
#         ai_msg_obj.file.save(filename, File(tmp_file), save=False)
#     ai_msg_obj.status = MessageObjectStatuses.IMAGE_READY
#     ai_msg_obj.save()
#     return True


# @app.task
# def update_user_onboarding_task(user_id, fields, token):
#     print(f"inside the update_user_onboarding_task: {token}")
#     """Task to send a PATCH request to update specific fields for the user's onboarding."""
#     url = f"{settings.USERS_SERVICE_URL}/users/onboarding_update/"
#     print(url)
#     headers = {
#         "Content-Type": "application/json",
#         "Authorization": f"Bearer {token}"
#     }

#     response = requests.patch(url, json=fields, headers=headers)

#     if response.status_code != 200:
#         print(f"Failed to update UserOnboarding for user "
#               "{user_id}: {response.content}")
#     else:
#         print(f"Successfully updated UserOnboarding for user {user_id}")
