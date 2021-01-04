import asyncio
import configparser
import logging.handlers
import os
import re
import sys

from datetime import datetime, timedelta

import telethon.events
from telethon.tl.functions.channels import EditBannedRequest, GetParticipantRequest, LeaveChannelRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import ChannelParticipantAdmin, ChatBannedRights

IN_DOCKER = os.getenv('DOCKER', False)


@telethon.events.register(telethon.events.ChatAction(func=lambda e: e.user_added or e.user_joined))
async def new_user(event: telethon.events.ChatAction.Event):
    for user in event.users:
        logger.debug('User %s added to %s', user.id, event.chat_id)
        if user.bot:
            if user.is_self:
                asyncio.create_task(handle_self_added(event))
            continue
        fulluser = await event.client(GetFullUserRequest(user))
        if fulluser.about and re.match(config['main']['regex'], fulluser.about):
            logger.info('Kicking %s from %s', user.id, event.chat_id)
            try:
                rights = ChatBannedRights(datetime.now() + timedelta(days=1), view_messages=True)
                await event.client(EditBannedRequest(event.input_chat, user, rights))
            except:
                logger.exception('Failed to ban user')
        else:
            logger.debug('User %s did not match', user.id)


async def handle_self_added(event: telethon.events.ChatAction.Event):
    logger.info('Bot added to %s', event.chat_id)
    bot = event.client

    if not event.chat.megagroup:
        try:
            await event.respond("Hello! Please note that I am only designed to work in supergroups. If you are unsure what this means"
                                " please view <a href='https://www.quora.com/What-is-a-telegram-group-or-supergroup?share=1'>this Quora page</a>",
                                parse_mode='HTML')
            logger.debug('Bot is leaving %s', event.chat_id)
            await bot(LeaveChannelRequest(event.input_chat))
        except:
            pass
        return

    req = GetParticipantRequest(event.input_chat, event.user_id)
    p = await bot(req)
    if not isinstance(p.participant, ChannelParticipantAdmin):
        logger.debug('Bot in %s does not have admin', event.chat_id)
        await event.respond("Hello! I noticed you have not added me as admin. Please grant the ban user permission so I may function properly")
        await asyncio.sleep(120)
        p = await bot(req)
    if not isinstance(p.participant, ChannelParticipantAdmin) or not p.participant.admin_rights.ban_users:
        logger.debug('Bot is leaving %s', event.chat_id)
        await bot(LeaveChannelRequest(event.input_chat))


@telethon.events.register(telethon.events.NewMessage(pattern='^/start', incoming=True, func=lambda e: e.is_private))
async def handle_pm(event: telethon.events.NewMessage.Event):
    await event.respond("Hello! I don't do anything in private, please add me to a group and grant ban permissions")


async def main(bot, token):
    await bot.connect()
    if not await bot.is_user_authorized() or not await bot.is_bot():
        await bot.start(bot_token=token)
    logger.info('Started bot')
    await bot.run_until_disconnected()


if __name__ == '__main__':
    if not os.path.exists('config.ini'):
        raise FileNotFoundError('config.ini not found. Please copy example-config.ini and edit the relevant values')
    config = configparser.ConfigParser()
    config.read_file(open('config.ini'))

    logger = logging.getLogger('bot')
    level = getattr(logging, config['main']['logging level'], logging.INFO)
    formatter = logging.Formatter("%(asctime)s\t%(levelname)s:%(message)s")
    logger.setLevel(level)

    if not os.path.exists('logs'):
        os.mkdir('logs', 0o770)
    logger.addHandler(logging.handlers.RotatingFileHandler(config['main']['logfile'], encoding='utf-8', maxBytes=5 * 1024 * 1024, backupCount=5))
    if IN_DOCKER:  # we are in docker, use stdout as well
        logger.addHandler(logging.StreamHandler(sys.stdout))

    for h in logger.handlers:
        h.setFormatter(formatter)
        h.setLevel(level)

    bot = telethon.TelegramClient(
        config['TG API']['session'],
        config['TG API'].getint('api_id'), config['TG API']['api_hash'],
        auto_reconnect=True, connection_retries=1000, flood_sleep_threshold=5
    )

    for h in (handle_pm, new_user):
        bot.add_event_handler(h)

    try:
        asyncio.get_event_loop().run_until_complete(main(bot, config['TG API']['bot_token']))
    except KeyboardInterrupt:
        pass
