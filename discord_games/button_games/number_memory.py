from __future__ import annotations

from typing import Optional
from io import BytesIO
import random
import string
import asyncio
import datetime
import pathlib

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from ..utils import *


class NumModal(discord.ui.Modal, title="Answer"):
    word = discord.ui.TextInput(
        label="number",
        style=discord.TextStyle.short,
        required=True,
        min_length=1,
    )

    def __init__(self, view: NumView) -> None:
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        game = self.view.game
        value = self.word.value
        assert game.embed

        if not value.isdigit():
            return await interaction.response.send_message(
                f"`{value}` is not a valid number!", ephemeral=True
            )

        if value == game.number:
            game.level += 1
            game.pause_time += game.pause_incr
            game.number = game.generate_number()
            await game.update_embed()
            self.view.answer.disabled = True

            files = [game.file] if game.file else discord.utils.MISSING
            await interaction.response.edit_message(
                attachments=files, embed=game.embed, view=self.view
            )

            await asyncio.sleep(game.pause_time)
            await game.update_embed(hide=True)

            if interaction.message:
                await interaction.message.edit(
                    attachments=[], embed=game.embed, view=self.view
                )
        else:
            game.embed.description = (
                "You Lost!\n\n```diff\nCorrect Number:\n"
                f"+ {game.number}\n"
                "Your Guess:\n"
                f"- {value}\n```"
            )
            self.view.disable_all()
            await interaction.response.edit_message(
                attachments=[], embed=game.embed, view=self.view
            )
            return self.view.stop()


class NumButton(discord.ui.Button["NumView"]):
    def __init__(self, label: str, style: discord.ButtonStyle) -> None:
        super().__init__(
            label=label,
            style=style,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view

        if self.label == "Cancel" and interaction.message:
            await interaction.message.delete()
            return self.view.stop()
        else:
            return await interaction.response.send_modal(NumModal(self.view))


class NumView(BaseView):
    def __init__(
        self,
        game: NumberMemory,
        *,
        button_style: discord.ButtonStyle = discord.ButtonStyle.blurple,
        timeout: Optional[float] = None,
    ) -> None:
        super().__init__(timeout=timeout)

        self.game = game
        self.button_style = button_style

        self.answer = NumButton(label="Answer", style=self.button_style)
        self.answer.disabled = True

        self.add_item(self.answer)
        self.add_item(NumButton(label="Cancel", style=discord.ButtonStyle.red))


class NumberMemory:
    def __init__(self, font_size: int = 30) -> None:
        self.file: Optional[discord.File] = None
        self.embed: Optional[discord.Embed] = None
        self.level = 1
        self.number = self.generate_number()

        self._text_size = font_size
        parent = pathlib.Path(__file__).parent.parent
        self._font = ImageFont.truetype(
            str(parent / "assets/ClearSans-Bold.ttf"), self._text_size
        )

    @executor()
    def generate_image(self) -> BytesIO:
        MARGIN = 3

        w, h = self._font.getsize(self.number)
        with Image.new("RGBA", (w + MARGIN * 2, h + MARGIN * 2), 0) as img:
            draw = ImageDraw.Draw(img)
            draw.text(
                (MARGIN, MARGIN), self.number, font=self._font, color=(255, 255, 255)
            )
            buf = BytesIO()
            img.save(buf, "PNG")
        buf.seek(0)
        return buf

    async def update_embed(self, hide: bool = False) -> None:
        assert self.embed
        self.embed.title = f"Level: `{self.level}`"

        if hide:
            self.view.answer.disabled = False
            self.embed.description = "```yml\nGuess!\n```"
            self.file = None
        else:
            time = discord.utils.utcnow() + datetime.timedelta(
                seconds=self.pause_time + 1
            )
            pause = discord.utils.format_dt(time, style="R")
            file = await self.generate_image()
            file = discord.File(file, "number.png")
            self.file = file

            self.embed.description = f"Guess in {pause}!"
            self.embed.set_image(url=f"attachment://{file.filename}")

    def generate_number(self) -> str:
        non_zero = list(string.digits)
        non_zero.remove("0")

        first = random.choice(non_zero)
        return first + "".join(random.choices(string.digits, k=self.level - 1))

    async def start(
        self,
        ctx: commands.Context[commands.Bot],
        *,
        initial_pause_time: float = 2.0,
        pause_time_increment: float = 1.0,
        button_style: discord.ButtonStyle = discord.ButtonStyle.blurple,
        embed_color: DiscordColor = DEFAULT_COLOR,
        timeout: Optional[float] = None,
    ) -> discord.Message:
        """
        starts the chimpanzee memory game test

        Parameters
        ----------
        ctx : commands.Context
            the context of the invokation command
        initial_pause_time : float
            the initial time the user gets to look at the number (1 digit) before they have to guess, by default 2.0
        pause_time_increment : float
            the increment by which the pause time is increased every level, by default 1.0
        button_style : discord.ButtonStyle, optional
            the button style to use for the game buttons, by default discord.ButtonStyle.blurple
        embed_color : DiscordColor, optional
            the color of the game embed, by default DEFAULT_COLOR
        timeout : Optional[float], optional
            the timeout for the view, by default None

        Returns
        -------
        discord.Message
            returns the game message
        """
        self.pause_incr = pause_time_increment
        self.pause_time = initial_pause_time

        self.embed = discord.Embed(color=embed_color)
        await self.update_embed()

        self.view = NumView(
            game=self,
            button_style=button_style,
            timeout=timeout,
        )
        if isinstance(ctx, discord.ext.commands.context.Context):
            self.message = await ctx.send(file=self.file, embed=self.embed, view=self.view)
        else:
            self.message = await ctx.interaction.send_message(file=self.file, embed=self.embed, view=self.view)


        await asyncio.sleep(self.pause_time)
        await self.update_embed(hide=True)

        await self.message.edit(attachments=[], embed=self.embed, view=self.view)

        await self.view.wait()
        return self.message
