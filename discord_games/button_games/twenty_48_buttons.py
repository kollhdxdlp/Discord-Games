from __future__ import annotations

from typing import Optional, Literal
import random

import discord
from discord.ext import commands

from ..twenty_48 import Twenty48
from ..utils import DiscordColor, DEFAULT_COLOR, BaseView


class BetaTwenty48(Twenty48):
    view: discord.ui.View
    """
    Twenty48(buttons) game
    """

    async def start(
        self,
        ctx: commands.Context[commands.Bot],
        *,
        win_at: Literal[2048, 4096, 8192] = 8192,
        timeout: Optional[float] = None,
        delete_button: bool = False,
        embed_color: DiscordColor = DEFAULT_COLOR,
        **kwargs,
    ) -> discord.Message:
        """
        starts the 2048(buttons) game

        Parameters
        ----------
        ctx : commands.Context
            the context of the invokation command
        win_at : Literal[2048, 4096, 8192], optional
            the tile to stop the game / win at, by default 8192
        timeout : Optional[float], optional
            the timeout for the view, by default None
        delete_button : bool, optional
            specifies whether or not to add a stop button, by default False
        embed_color : DiscordColor, optional
            the color of the game embed, by default DEFAULT_COLOR

        Returns
        -------
        discord.Message
            returns the game message
        """
        self.win_at = win_at
        self.embed_color = embed_color
        if isinstance(ctx, discord.ext.commands.context.Context):
            self.player = ctx.author
        else:
            self.player = ctx.user
        self.view = BaseView(timeout=timeout)

        self.board[random.randrange(4)][random.randrange(4)] = 2
        self.board[random.randrange(4)][random.randrange(4)] = 2

        #not using self._controls because of the order
        controls = ["", "⬆", "","⬅","⬇","➡"]

        for buttonID in range(6):
            if buttonID == 0 and delete_button:
                emoji = "⏹️"
                style = discord.ButtonStyle.red
                disabled = False
            elif buttonID in [0, 2]:
                emoji = None
                style = discord.ButtonStyle.gray
                disabled = True
            else:
                emoji = controls[buttonID]
                style = discord.ButtonStyle.blurple
                disabled = False

            button = discord.ui.Button(label = "\u200b", emoji=emoji, style=style, disabled=disabled)
            button.callback = self.callback
            self.view.add_item(button)

        if self._render_image:
            image = await self.render_image()
            if isinstance(ctx, discord.ext.commands.context.Context):
                self.message = await ctx.send(file=image, view=self.view, **kwargs)
            else:
                self.message = await ctx.interaction.send_message(file=image, view=self.view, **kwargs)
        else:
            board_string = self.number_to_emoji()
            if isinstance(ctx, discord.ext.commands.context.Context):
                self.message = await ctx.send(content=board_string, view=self.view, **kwargs)
            else:
                self.message = await ctx.interaction.send_message(content=board_string, view=self.view, **kwargs)

        await self.view.wait()
        return self.message
    
    async def callback(self, interaction: discord.Interaction) -> None:

        if interaction.user != self.game.player:
            return await interaction.response.send_message(
                "This isn't your game!", ephemeral=True
            )

        emoji = str(self.emoji)

        if emoji == "⏹️":
            self.view.stop()
            return await interaction.message.delete()

        elif emoji == "➡️":
            self.game.move_right()

        elif emoji == "⬅️":
            self.game.move_left()

        elif emoji == "⬇️":
            self.game.move_down()

        elif emoji == "⬆️":
            self.game.move_up()

        lost = self.game.spawn_new()
        won = self.game.check_win()

        if won or lost:
            self.view.disable_all()
            self.view.stop()

        if lost:
            self.game.embed = discord.Embed(
                description="Game Over! You lost.",
                color=self.game.embed_color,
            )

        if self.game._render_image:
            image = await self.game.render_image()
            await interaction.response.edit_message(
                attachments=[image], embed=self.game.embed
            )
        else:
            board_string = self.game.number_to_emoji()
            await interaction.response.edit_message(
                content=board_string, embed=self.game.embed
            )
