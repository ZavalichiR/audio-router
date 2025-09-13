"""
Information and status command handlers for the main bot.

This module contains commands that provide information about the system,
subscription status, and bot status.
"""

import json
import re

import discord
from discord.ext import commands

from discord_audio_router.bots.commands.base import BaseCommandHandler
from discord_audio_router.bots.utils.embed_builder import EmbedBuilder
from discord_audio_router.subscription.models import ServerSubscription


class InfoCommands(BaseCommandHandler):
    """Handles all information and status commands."""

    async def help_command(self, ctx: commands.Context) -> None:
        """Show all available commands and their descriptions."""
        embed = EmbedBuilder.help_command()
        await ctx.send(embed=embed)

    async def how_it_works_command(self, ctx: commands.Context) -> None:
        """Explain how the audio routing system works."""
        embed = EmbedBuilder.how_it_works()
        await ctx.send(embed=embed)

    async def subscription_status_command(self, ctx: commands.Context) -> None:
        """Check the subscription status for this server."""
        try:
            if not self.subscription_manager:
                await ctx.send(
                    embed=EmbedBuilder.warning(
                        "Subscription System Loading",
                        "The subscription system is still initializing. Please wait a moment and try again.\n\nIf this persists, contact the bot administrator.",
                    )
                )
                return

            server_id = str(ctx.guild.id)
            subscription = self.subscription_manager.get_server_subscription(server_id)

            if subscription:
                embed = self._build_subscription_embed(ctx, subscription)
            else:
                embed = self._build_default_subscription_embed(ctx)

            # Add available tiers
            embed = self._add_available_tiers(embed)
            await ctx.send(embed=embed)

        except Exception as e:
            await self._handle_command_error(ctx, e, "subscription_status")

    async def bot_status_command(self, ctx: commands.Context) -> None:
        """Check the status of installed receiver bots in this server."""
        try:
            configured_tokens = (
                len(self.config.audio_receiver_tokens) if hasattr(self, "config") else 0
            )
            installed_bots = await self._get_available_receiver_bots_count(ctx.guild)

            if self.subscription_manager:
                max_allowed = self.subscription_manager.get_server_max_listeners(
                    str(ctx.guild.id)
                )
                if max_allowed == 0:
                    max_allowed = configured_tokens
            else:
                max_allowed = 1

            # Get bot information
            bot_info = await self._get_bot_information(ctx.guild)
            active_bot_info = self._get_active_bot_info()

            # Build status text
            status_text = self._build_bot_status_text(
                bot_info, installed_bots, max_allowed, active_bot_info
            )

            embed = EmbedBuilder.info("Bot Status", status_text)

            # Add invite links and recommendations
            embed = await self._add_bot_recommendations(
                embed, installed_bots, max_allowed
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await self._handle_command_error(ctx, e, "bot_status")

    def _build_subscription_embed(
        self, ctx: commands.Context, subscription: ServerSubscription
    ) -> discord.Embed:
        """Build subscription status embed for existing subscription."""

        tier_info = self.subscription_manager.get_tier_info(subscription.tier)
        tier_descriptions = {
            "Free": "Basic functionality",
            "Basic": "Trial tier",
            "Standard": "Small communities",
            "Advanced": "Medium communities",
            "Premium": "Large communities",
            "Custom": "Custom features",
        }
        tier_request_channels = {
            "Free": "-",
            "Basic": "-",
            "Standard": "-",
            "Advanced": "email",
            "Premium": "email",
            "Custom": "DM or email",
        }

        tier_name = tier_info["name"]
        description = tier_descriptions.get(tier_name, "Unknown")
        request_channel = tier_request_channels.get(tier_name, "Unknown")

        embed = EmbedBuilder.success(
            "Subscription Status",
            f"**Server:** {ctx.guild.name}\n**Server ID:** {str(ctx.guild.id)}",
        )

        if request_channel != "-":
            current_tier_value = (
                f"**{tier_name}** - {description} (request via {request_channel})"
            )
        else:
            current_tier_value = f"**{tier_name}** - {description}"

        embed.add_field(
            name="🎯 Current Tier",
            value=current_tier_value,
            inline=False,
        )

        embed.add_field(
            name="📢 Listener Limit",
            value=f"**{subscription.max_listeners}** listener channel{'s' if subscription.max_listeners != 1 else ''}"
            if subscription.max_listeners > 0
            else "**Unlimited** listeners",
            inline=True,
        )

        embed.add_field(
            name="📅 Subscription Info",
            value=f"**Created:** {subscription.created_at or 'Unknown'}\n**Updated:** {subscription.updated_at or 'Unknown'}",
            inline=True,
        )

        return embed

    def _build_default_subscription_embed(self, ctx: commands.Context) -> discord.Embed:
        """Build subscription status embed for default (no subscription)."""
        from discord_audio_router.subscription.models import SubscriptionTier

        tier_info = self.subscription_manager.get_tier_info(SubscriptionTier.FREE)

        embed = EmbedBuilder.info(
            "Subscription Status",
            f"**Server:** {ctx.guild.name}\n**Server ID:** {str(ctx.guild.id)}",
        )

        embed.add_field(
            name="🎯 Current Tier",
            value=f"**{tier_info['name']}** (Default) - Basic functionality",
            inline=False,
        )

        embed.add_field(
            name="📢 Listener Limit",
            value=f"**{tier_info['max_listeners']}** listener channel",
            inline=True,
        )

        embed.add_field(
            name="💡 Upgrade Available",
            value="Contact **zavalichir** or visit our website (URL TBD) to upgrade your subscription!",
            inline=True,
        )

        return embed

    def _add_available_tiers(self, embed: discord.Embed) -> discord.Embed:
        """Add available subscription tiers to embed."""
        from discord_audio_router.subscription.models import SUBSCRIPTION_TIERS

        tier_descriptions = {
            "Free": "Basic functionality",
            "Basic": "Trial tier",
            "Standard": "Small communities",
            "Advanced": "Medium communities",
            "Premium": "Large communities",
            "Custom": "Custom features",
        }
        tier_request_channels = {
            "Free": "-",
            "Basic": "-",
            "Standard": "-",
            "Advanced": "email",
            "Premium": "email",
            "Custom": "DM or email",
        }

        tiers_text = "\n".join(
            [
                (
                    f"• **{info['name']}**: "
                    f"{info['max_listeners'] if info['max_listeners'] > 0 else 'unlimited'} listeners - "
                    f"{tier_descriptions.get(info['name'], 'Unknown')}"
                    + (
                        f" (request via {tier_request_channels.get(info['name'], 'Unknown')})"
                        if tier_request_channels.get(info["name"], "Unknown")
                        not in ("Unknown", "-")
                        else ""
                    )
                )
                for _, info in SUBSCRIPTION_TIERS.items()
            ]
        )

        embed.add_field(
            name="📋 Available Tiers",
            value=tiers_text,
            inline=False,
        )

        return embed

    async def _get_bot_information(self, guild: discord.Guild) -> dict:
        """Get information about installed bots."""
        try:
            members = [member async for member in guild.fetch_members(limit=None)]
            main_bot_name = guild.me.display_name
            forwarder_bot_name = "Not found"
            receiver_bot_names = []

            def extract_rcv_number(name):
                match = re.match(r"Rcv-(\d+)", name)
                return int(match.group(1)) if match else float("inf")

            for member in members:
                if member.bot:
                    if member.display_name.startswith("Rcv-"):
                        receiver_bot_names.append(member.display_name)
                    elif "forward" in member.display_name.lower():
                        forwarder_bot_name = member.display_name
            receiver_bot_names.sort(key=extract_rcv_number)

            return {
                "main_bot": main_bot_name,
                "forwarder": forwarder_bot_name,
                "receivers": receiver_bot_names,
            }
        except Exception as e:
            self.logger.error(f"Error fetching bot info: {e}")
            return {
                "main_bot": guild.me.display_name,
                "forwarder": "Unknown",
                "receivers": [],
            }

    def _get_active_bot_info(self) -> str:
        """Get information about active bot processes."""
        if self.audio_router:
            process_status = self.audio_router.bot_manager.get_status()
            return f"\n**Active Bot Processes:** {process_status['alive_processes']}/{process_status['total_processes']}\n"
        return ""

    def _build_bot_status_text(
        self,
        bot_info: dict,
        installed_bots: int,
        max_allowed: int,
        active_bot_info: str,
    ) -> str:
        """Build the main bot status text."""
        status_text = f"**Main Bot:** {bot_info['main_bot']}\n"
        status_text += f"**Forwarder:** {bot_info['forwarder']}\n"
        status_text += f"**Receivers:** {', '.join(bot_info['receivers']) if bot_info['receivers'] else 'None'}\n\n"
        status_text += f"**Status:** {installed_bots}/{max_allowed} receivers installed (subscription limit)"
        status_text += active_bot_info
        return status_text

    async def _add_bot_recommendations(
        self, embed: discord.Embed, installed_bots: int, max_allowed: int
    ) -> discord.Embed:
        """Add bot installation recommendations to embed."""
        try:
            with open("data/bot_urls.json", "r", encoding="utf-8") as f:
                invite_links = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load bot URLs: {e}")
            invite_links = []

        if installed_bots < max_allowed:
            missing_bots = max_allowed - installed_bots
            embed.add_field(
                name="⚠️ Missing Receivers",
                value=f"Need {missing_bots} more receiver{'s' if missing_bots > 1 else ''} for your subscription tier. Install with these links:",
                inline=False,
            )

            first_missing_bot = installed_bots + 1
            last_available_bot = min(max_allowed, len(invite_links))

            for bot_number in range(first_missing_bot, last_available_bot + 1):
                link_index = bot_number - 1
                embed.add_field(
                    name=f"Rcv-{bot_number}",
                    value=f"[Install Bot]({invite_links[link_index]})",
                    inline=False,
                )

            if max_allowed > len(invite_links):
                first_contact_bot = len(invite_links) + 1
                embed.add_field(
                    name="📞 Contact for More Bots",
                    value=f"For receivers Rcv-{first_contact_bot} to Rcv-{max_allowed}, please contact **zavalichir** to get additional receiver bots.",
                    inline=False,
                )
            embed.color = discord.Color.orange()

        elif installed_bots > max_allowed:
            extra_bots = installed_bots - max_allowed
            embed.add_field(
                name="ℹ️ Extra Receivers",
                value=f"You have {extra_bots} extra receiver{'s' if extra_bots > 1 else ''} installed. Receivers {max_allowed + 1}-{installed_bots} can be removed if not needed.",
                inline=False,
            )
            embed.color = discord.Color.blue()
        else:
            embed.add_field(
                name="✅ Perfect",
                value="All required receivers for your subscription tier are installed!",
                inline=False,
            )
            embed.color = discord.Color.green()

        return embed
