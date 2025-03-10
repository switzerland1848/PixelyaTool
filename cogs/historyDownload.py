#!/usr/bin/python3
import discord
from discord import app_commands
from discord.ext import commands
from enum import Enum
import PIL.Image
import sys, io, os
import datetime
import asyncio, aiohttp
import datetime
import traceback, logging
import subprocess, platform


USER_AGENT = "pyf areaDownload 1.0 0 -1_-1 1_1 2024-07-13 2024-07-14"
PYF_URL = "https://pixelya.fun"
PYF_STORAGE_URL = "https://storage.pixelya.fun/history"

async def fetchMe():
    url = f"{PYF_URL}/api/me"
    headers = {
      'User-Agent': USER_AGENT
    }
    async with aiohttp.ClientSession() as session:
        attempts = 0
        while True:
            try:
                async with session.get(url, headers=headers) as resp:
                    data = await resp.json()
                    return data
            except:
                if attempts > 3:
                    logging.warning(f"Could not get {url} in three tries, cancelling")
                    raise
                attempts += 1
                logging.warning(f"Failed to load {url}, trying again in 5s")
                await asyncio.sleep(5)
                pass
            
async def fetch(session, url, offx, offy, image, bkg, needed = False):
    attempts = 0
    headers = {
      'User-Agent': USER_AGENT
    }
    while True:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 404:
                    if needed:
                        img = PIL.Image.new('RGB', (256, 256), color=bkg)
                        image.paste(img, (offx, offy))
                        # img.close()
                    return
                if resp.status != 200:
                    if needed:
                        continue
                    return
                data = await resp.read()
                img = PIL.Image.open(io.BytesIO(data)).convert('RGBA')
                image.paste(img, (offx, offy), img)
                # img.close()
                return
        except:
            if attempts > 3:
                raise
            attempts += 1
            pass

async def get_area(canvas_id, canvas, x, y, w, h, start_date, end_date, thread, form):
    list_gif = []
    gifilename = "%s.gif"%(thread.name)
    canvas_size = canvas["size"]
    bkg = tuple(canvas['colors'][0])
    delta = datetime.timedelta(days=1)
    end_date = end_date.strftime("%Y%m%d")
    iter_date = None
    cnt = 0
    previous_day = PIL.Image.new('RGB', (w, h), color=bkg)
    while iter_date != end_date:
        iter_date = start_date.strftime("%Y%m%d")
        logging.debug('------------------------------------------------')
        logging.debug('Getting data for date %s' % (iter_date))
        start_date = start_date + delta

        fetch_canvas_size = canvas_size
        if 'historicalSizes' in canvas:
            for ts in canvas['historicalSizes']:
                date = ts[0]
                size = ts[1]
                if iter_date <= date:
                    fetch_canvas_size = size

        offset = int(-fetch_canvas_size / 2)
        xc = (x - offset) // 256
        wc = (x + w - offset) // 256
        yc = (y - offset) // 256
        hc = (y + h - offset) // 256
        logging.debug("Load from %s / %s to %s / %s with canvas size %s" % (xc, yc, wc + 1, hc + 1, fetch_canvas_size))

        tasks = []
        async with aiohttp.ClientSession() as session:
            image = PIL.Image.new('RGBA', (w, h))
            for iy in range(yc, hc + 1):
                for ix in range(xc, wc + 1):
                    url = '%s/%s/%s/%s/%s/tiles/%s/%s.png' % (PYF_STORAGE_URL, iter_date[0:4], iter_date[4:6] , iter_date[6:], canvas_id, ix, iy)
                    offx = ix * 256 + offset - x
                    offy = iy * 256 + offset - y
                    tasks.append(fetch(session, url, offx, offy, image, bkg, True))
            await asyncio.gather(*tasks)
            logging.debug('Got start of day')

            clr = image.getcolors(1)
            if clr is not None:
                logging.debug("Got faulty full-backup frame, using last frame from previous day instead.")
                image = previous_day.copy()
            cnt += 1

            image_binary = io.BytesIO()
            image.save(image_binary, 'PNG')
            image_binary.seek(0)
            if form == "img" :
                await thread.send(f"Frame number {cnt}", file = discord.File(fp = image_binary, filename = "Frame%s.png"%(cnt)))
            elif form == "gif" :
                list_gif.append(image)

            headers = {
                'User-Agent': USER_AGENT
            }
            while True:
                if int(iter_date) < 20240724 and canvas_id == 5 : # Pixelya does not have any data to dates prior this. (world)
                    logging.debug("Pixelya does not have any data to dates prior this.")
                    return await thread.send(f"\nSeems like you selected a date before 2024/07/24, therefore the script can't run because Pixelya does not have any data prior to this date on World canvas.\n")
                elif int(iter_date) < 20240118 and canvas_id in[0, 1] : # Pixelya does not have any data for these dates too (miniworld, graffiti)
                    logging.debug("Pixelya does not have any data to dates prior this.")
                    return await thread.send(f"\nSeems like you selected a date before 2024/01/18, therefore the script can't run because Pixelya does not have any data prior to this date on miniworld and graffiti canvas.\n")
                elif int(iter_date) < 20240720 and canvas_id == 6 : # Pixelya does not have any data for these dates too (top15)
                    logging.debug("Pixelya does not have any data to dates prior this.")
                    return await thread.send(f"\nSeems like you selected a date before 2024/07/20, therefore the script can't run because Pixelya does not have any data prior to this date in top15 canvas.\n")
                elif canvas_id == 2 and (int(iter_date) <20240115 or int(iter_date) >20240701) : # football canvas
                    logging.debug("Pixelya does not have any data to dates prior this.")
                    return await thread.send(f"\nSeems like you selected a date before 2024/01/15 or after 2024/07/01, therefore the script can't run because Pixelya does not have any data outside these dates for footbal canvas (archived).\n")

                async with session.get('%s/history?day=%s&id=%s' % (PYF_URL, iter_date, canvas_id), headers=headers) as resp:
                    try:
                        time_list = await resp.json()
                        break
                    except:
                        logging.warning('Couldn\'t decode json for day %s, trying again' % (iter_date))
            i = 0
            for time in time_list:
                i += 1
                if (i % 1) != 0:
                    continue
                if time == '0000':
                    continue
                tasks = []
                image_rel = image.copy()
                for iy in range(yc, hc + 1):
                    for ix in range(xc, wc + 1):
                        url = '%s/%s/%s/%s/%s/%s/%s/%s.png' % (PYF_STORAGE_URL, iter_date[0:4], iter_date[4:6] , iter_date[6:], canvas_id, time, ix, iy)
                        offx = ix * 256 + offset - x
                        offy = iy * 256 + offset - y
                        tasks.append(fetch(session, url, offx, offy, image_rel, bkg))
                await asyncio.gather(*tasks)
                logging.debug('Got data from time %s' % (time))
                cnt += 1
                image_rel_binary = io.BytesIO() # ? WORKS ?
                image_rel.save(image_rel_binary, 'PNG')
                image_rel_binary.seek(0)
                if form == "img" :
                    await thread.send(f"Frame number {cnt}", file = discord.File(fp = image_rel_binary, filename = "Frame%s.png"%(cnt)))
                elif form == "gif" :
                    list_gif.append(image_rel)

                if time == time_list[-1]:

                    previous_day.close()
                    previous_day = image_rel.copy();
    if len(list_gif) != 0 :
        gif = list_gif[0].save(gifilename, save_all = True, append_images = list_gif[1:], optimize=True, loop=0)
        await thread.send("Final Gif image :", file = discord.File(gifilename))
        if platform.system() == "Linux" :
            subprocess.run(['rm', gifilename])
        elif platform.system() == "Windows":
            subprocess.run(['del',gifilename])


class historyDownload(commands.Cog):
    def __init__(self, bot : commands.Bot) -> None:
        self.bot = bot
        logging.basicConfig(filename = "historyDownload.log", level = logging.INFO, format = "%(asctime)s:%(levelname)s:%(message)s")


    @commands.Cog.listener(name="on_ready")
    async def CogLoaded(self) -> None:
        return logging.info("history Download Cog loaded")
    
    group = app_commands.Group(name="history", description="Area Download related commands")

    canvas = {'Mini World': '0', 'Graffiti': '1', 'Football': '2', 'World': '5', 'Top 15': '6'}
    @group.command(name = "refresh", description = "Refresh canvases options for the commands")  
    async def refreshing_canvas_list(self, interaction : discord.Interaction):
        if not interaction.user.guild_permissions.administrator :
            return await interaction.response.send_message("You do not have the permissions to use this command")
        logging.info(f"{interaction.user} has reloaded the canvas list")
        apime = await fetchMe()
        canvases = apime['canvases'].items()
        global canvas
        canvas = { can[1]['title'] :can[0]  for can in canvases}
        logging.debug(canvas)
        return await interaction.response.send_message(f"Canvases list has been updated : {canvas}")

    @group.command(name = "infos", description = r"Information on how to use `/history download`")
    async def info_history_download(self, interaction : discord.Interaction):
        logging.info(f"information comment send by {interaction.user}")
        apime = await fetchMe()
        informations = discord.Embed(
            title="Download all tiles of an area of pixelya between two dates",
            description="Here is an explaination on how to use this command without making the bot sending an error message :",
            url="https://www.pixelya.fun",
            color=discord.Color.from_rgb(148, 224, 0),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        global canvas
        canvases = apime['canvases'].items()
        informations.add_field(name="Maps", value=f"Here are the available canvases : {' ; '.join(self.canvas.keys())}", inline = False)

        informations.add_field(name="Coordinates", value = "Use `R` key in the canvas to pick coordinates. You need the Upper left corner (startx_starty) and the bottom right corner (endx_endy)", inline = False)

        informations.add_field(name = "Dates", value = "Give the starting date (older one) and then the ending date (most recent one) in the following format : YYYY-MM-DD", inline = False)

        informations.add_field(name = "Result", value = "The bot will send you the result as several image in a thread under the command. If it doesn't work and you have made no mistakes, please make a bug report in the dedicated thread of this channel", inline = False)

        informations.set_author(name=self.bot.user.display_name, url = "https://github.com/Daeltam/PyfDownloadTool", icon_url=self.bot.user.avatar)
        informations.set_footer(text = "Informations about /history Download")

        return await interaction.response.send_message(embed=informations)
    
    mapsEnum = Enum('maps', canvas)
    @app_commands.choices(
                        privacy = [app_commands.Choice(name = "Private", value = 0), 
                                     app_commands.Choice(name = "Public", value = 1)],
                        form = [app_commands.Choice(name = "Several Images", value = "img"),
                                  app_commands.Choice(name = "Gif file", value = "gif"),
                                  app_commands.Choice(name = "Video file", value = "vid")]
                        )
    @group.command(name = "download", description = "Sends the pixelya maps between two coordinates and two dates in a thread.")
    @app_commands.describe(maps = "Map from which you want to download the image",
                           startx_starty = "Top left coordinates in the good format",
                           endx_endy = "Bottom right coordinates in the good format",
                           start_date = "Starting date in the YYYY-MM-DD format",
                           end_date = "Ending date in the YYYY-MM-DD format, automatically set as today",
                           form = "Wether you want it to be shown as several images, a gif file or a video file",
                           privacy = "Defines if the images will be sent in a public or a private thread. You will be pentionned in the private thread when all the images will be finished")
    async def download_area(self,
                            interaction : discord.Interaction, 
                            maps : mapsEnum, 
                            startx_starty : str, 
                            endx_endy : str, 
                            start_date : str, 
                            end_date : str = "today", 
                            form : app_commands.Choice[str] = "gif",
                            privacy : app_commands.Choice[int] = 0):
        global USER_AGENT
        USER_AGENT = "pyf areaDownload 1.0 " + maps.value + " " + startx_starty + " " + endx_endy + " " + start_date + " " + end_date
        logging.info(f"downloadArea called by {interaction.user} with parameters : {startx_starty},{endx_endy}, {start_date},{end_date}, {form.name}")
        await interaction.response.send_message("<a:loading:1267469203103940673> Your image is being processed, please wait")

        if form.value == "vid":
            return await interaction.edit_original_response(content = "Video file is not available yet, only gif and frame format. Sorry for the inconvenience")

        thread : discord.Thread
        if privacy.value == 1 :
            thread = await interaction.channel.create_thread(
                name = f"{interaction.user.name}'s History download on {datetime.date.today()}",
                auto_archive_duration=10080,
                slowmode_delay=None,
                reason = f"{interaction.user}'s history file",
                type=discord.ChannelType.public_thread,
                invitable=True)
        elif privacy.value == 0 : # * Default value
            thread = await interaction.channel.create_thread(
                name = f"{interaction.user.name}'s History download on {datetime.date.today()}",
                auto_archive_duration=10080,
                slowmode_delay=None,
                reason = f"{interaction.user}'s history file",
                type=discord.ChannelType.private_thread,
                invitable=True)
        try :
            apime = await fetchMe()
            canvas_id = maps.value

            if canvas_id not in apime['canvases']:
                return await interaction.edit_original_response("❌ Invalid canvas selected")
            canvas_infos = apime['canvases'][canvas_id]
            start = startx_starty.split('_')
            end = endx_endy.split('_')
            try :
                start_date = datetime.date.fromisoformat(start_date)
                if end_date == "today":
                    end_date = datetime.date.today()
                else:
                    end_date = datetime.date.fromisoformat(end_date)
                if end_date < start_date:
                    return await interaction.edit_original_response(content = "your end date is prior to your start date, this won't work.")
                elif end_date > datetime.date.today():
                    return await interaction.edit_original_response(content = "You cannot download an image that hasn't been created yet, please don't try to time travel with my poor bot.")
            except :
                error_message= "<a:error40:1267490066125819907> Your date format is wrong and created an error, please make sure to use the YYYY-MM-DD format."
                return await interaction.edit_original_response(content = error_message)
            x = int(start[0])
            y = int(start[1])
            w = int(end[0]) - x + 1
            h = int(end[1]) - y + 1

            # subprocess.run("echo >  %s.gif"%(thread.name))
            await get_area(canvas_id, canvas_infos, x, y, w, h, start_date, end_date, thread, form.value) # SEND IMAGE IN GET_AREA
            await thread.send(f"{interaction.user.mention}, your images are here !")
            logging.info("Download completed !")
            print("Download completed !")
            try :
                await interaction.edit_original_response(content = f"<a:shiny:1267483837148037190> {interaction.user.mention} Your images are ready, thank you for waiting ! You can find them here : {thread.mention} ")
            except discord.app_commands.errors.CommandInvokeError:
                await interaction.original_response().delete()
                await interaction.channel.send(f"<a:shiny:1267483837148037190> {interaction.user.mention} Your images are ready, thank you for waiting ! You can find them here : {thread.mention} ", silent = True)
        except Exception:
            print(traceback.print_exc())
            logging.exception(f'Exception when running /area Download')
            await interaction.edit_original_response(content = "<a:error40:1267490066125819907> Something went wrong, your image will not be delivered, please report a bug in the dedicated thread.")

async def setup(bot):
    await bot.add_cog(historyDownload(bot))