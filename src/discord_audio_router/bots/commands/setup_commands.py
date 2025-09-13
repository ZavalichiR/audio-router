"""
Setup and configuration command handlers for the main bot.

This module contains commands related to server setup, role management,
and permission checking.
"""

from typing import Optional
import discord
from discord.ext import commands

from discord_audio_router.bots.commands.base import BaseCommandHandler
from discord_audio_router.bots.utils.embed_builder import EmbedBuilder


class SetupCommands(BaseCommandHandler):
    """Handles all setup and configuration commands."""

    async def setup_roles_command(self, ctx: commands.Context) -> None:
        """Create and configure the required roles for the audio router system."""
        try:
            if not self.audio_router or not hasattr(
                self.audio_router, "access_control"
            ):
                await ctx.send(
                    embed=EmbedBuilder.warning(
                        "System Loading",
                        "The access control system is still initializing. Please wait a moment and try again.",
                    )
                )
                return

            await ctx.send(
                embed=EmbedBuilder.info(
                    "Setting Up Roles", "Creating and configuring required roles..."
                )
            )

            roles = await self.audio_router.access_control.ensure_roles_exist(ctx.guild)
            speaker_role = roles.get("speaker_role")
            listener_role = roles.get("listener_role")
            broadcast_admin_role = roles.get("broadcast_admin_role")

            # Handle role positioning
            await self._handle_role_positioning(
                ctx, speaker_role, listener_role, broadcast_admin_role
            )

            # Build and send result embed
            result_embed = self._build_role_setup_result(
                ctx, speaker_role, broadcast_admin_role
            )
            await ctx.send(embed=result_embed)

        except Exception as e:
            await self._handle_command_error(ctx, e, "setup_roles")

    async def check_setup_command(self, ctx: commands.Context) -> None:
        """🔍 Check if your server is properly configured for the Audio Router Bot."""
        try:
            if not self.audio_router:
                await self._send_system_starting_embed(ctx)
                return

            embed = EmbedBuilder.info(
                "Server Setup Check", "Checking your server configuration..."
            )

            # Check bot permissions
            permission_status = self._check_bot_permissions(ctx)
            embed.add_field(
                name="🤖 Bot Permissions",
                value="\n".join(permission_status),
                inline=False,
            )

            # Check required roles
            role_status = self._check_required_roles(ctx)
            embed.add_field(
                name="👥 Required Roles", value="\n".join(role_status), inline=False
            )

            # Check active section
            active_section_info = self._check_active_section(ctx)
            embed.add_field(
                name="📊 Active Broadcast Section",
                value=active_section_info,
                inline=False,
            )

            # Check for issues and provide fixes
            issues = self._identify_setup_issues(ctx, role_status)
            if issues:
                embed = self._add_issues_to_embed(embed, issues)
            else:
                embed = self._add_success_to_embed(embed)

            await ctx.send(embed=embed)

        except Exception as e:
            await self._handle_command_error(ctx, e, "check_setup")

    async def check_permissions_command(self, ctx: commands.Context) -> None:
        """Check bot permissions and provide step-by-step fixes."""
        try:
            bot_member = ctx.guild.me
            perms = bot_member.guild_permissions

            embed = EmbedBuilder.info(
                "Bot Permission Analysis",
                "Analyzing bot permissions and role hierarchy...",
            )

            # Check permissions
            permissions = self._get_permission_checks()
            permission_status, missing_permissions = self._analyze_permissions(
                perms, permissions
            )
            embed.add_field(
                name="📋 Current Permissions",
                value="\n".join(permission_status),
                inline=False,
            )

            # Check role hierarchy
            embed.add_field(
                name="👑 Bot Role Position",
                value=f"**Bot Role:** {bot_member.top_role.name}\n"
                f"**Position:** {bot_member.top_role.position} (higher = more permissions)\n"
                f"**Total Roles:** {len(ctx.guild.roles)}",
                inline=False,
            )

            # Check role management
            role_management_status = self._check_role_management(ctx, bot_member)
            embed.add_field(
                name="🎭 Role Management",
                value="\n".join(role_management_status),
                inline=False,
            )

            # Add fixes or success message
            if missing_permissions or not perms.administrator:
                embed = self._add_permission_fixes(embed, missing_permissions)
            else:
                embed = self._add_permission_success(embed)

            # Check role hierarchy issues
            if bot_member.top_role.position < 3:
                embed = self._add_hierarchy_warning(embed)

            await ctx.send(embed=embed)

        except Exception as e:
            await self._handle_command_error(ctx, e, "check_permissions")

    async def role_info_command(self, ctx: commands.Context) -> None:
        """Show information about the audio router roles and how to use them."""
        try:
            if not self.audio_router or not hasattr(
                self.audio_router, "access_control"
            ):
                await ctx.send(
                    embed=EmbedBuilder.warning(
                        "System Loading",
                        "The access control system is still initializing. Please wait a moment and try again.",
                    )
                )
                return

            speaker_role = discord.utils.get(
                ctx.guild.roles, name=self.audio_router.access_control.speaker_role_name
            )
            broadcast_admin_role = discord.utils.get(
                ctx.guild.roles,
                name=self.audio_router.access_control.broadcast_admin_role_name,
            )

            embed = EmbedBuilder.info(
                "Audio Router Role Information",
                "Learn about the roles used by the audio router system:",
            )

            # Add role information
            embed = self._add_speaker_role_info(embed, speaker_role, ctx.guild)
            embed = self._add_broadcast_admin_role_info(
                embed, broadcast_admin_role, ctx.guild
            )
            embed = self._add_role_system_explanation(embed)
            embed = self._add_usage_examples(embed)

            # Add next steps or success message
            if not speaker_role or not broadcast_admin_role:
                embed = self._add_setup_next_steps(embed)
            else:
                embed = self._add_ready_to_use(embed)

            await ctx.send(embed=embed)

        except Exception as e:
            await self._handle_command_error(ctx, e, "role_info")

    async def _handle_role_positioning(
        self,
        ctx: commands.Context,
        speaker_role: Optional[discord.Role],
        listener_role: Optional[discord.Role],
        broadcast_admin_role: Optional[discord.Role],
    ) -> None:
        """Handle positioning of roles in the hierarchy."""
        bot_member = ctx.guild.me
        bot_role = bot_member.top_role

        roles_to_move: list[tuple[str, discord.Role]] = []
        if listener_role and listener_role.position >= bot_role.position:
            roles_to_move.append(("Listener", listener_role))
        if speaker_role and speaker_role.position >= bot_role.position:
            roles_to_move.append(("Speaker", speaker_role))
        if broadcast_admin_role and broadcast_admin_role.position >= bot_role.position:
            roles_to_move.append(("Broadcast Admin", broadcast_admin_role))

        if roles_to_move:
            try:
                target_position = max(0, bot_role.position - 1)
                for role_name, role in roles_to_move:
                    if role.position >= bot_role.position:
                        await role.edit(position=target_position)
                        self.logger.info(
                            f"Moved {role_name} role to position {target_position}"
                        )
                        target_position -= 1
            except discord.Forbidden:
                self.logger.warning("Could not move roles - insufficient permissions")
            except Exception as e:
                self.logger.error(f"Error moving roles: {e}", exc_info=True)

    def _build_role_setup_result(
        self,
        ctx: commands.Context,
        speaker_role: Optional[discord.Role],
        broadcast_admin_role: Optional[discord.Role],
    ) -> discord.Embed:
        """Build the role setup result embed."""
        result_embed = EmbedBuilder.success(
            "Role Setup Complete", "Required roles have been created and configured:"
        )

        # Add speaker role info
        if speaker_role:
            member_count = sum(1 for m in ctx.guild.members if speaker_role in m.roles)
            result_embed.add_field(
                name="🎤 Speaker Role",
                value=f"✅ {speaker_role.mention}\n"
                f"**Purpose:** Required to join speaker channels\n"
                f"**Members:** {member_count} users\n"
                f"**Position:** {speaker_role.position}",
                inline=False,
            )
        else:
            result_embed.add_field(
                name="🎤 Speaker Role",
                value="❌ Failed to create speaker role",
                inline=False,
            )

        # Add broadcast admin role info
        if broadcast_admin_role:
            member_count = sum(
                1 for m in ctx.guild.members if broadcast_admin_role in m.roles
            )
            result_embed.add_field(
                name="🎛️ Broadcast Admin Role",
                value=f"✅ {broadcast_admin_role.mention}\n"
                f"**Purpose:** Required to use bot commands\n"
                f"**Members:** {member_count} users\n"
                f"**Position:** {broadcast_admin_role.position}",
                inline=False,
            )
        else:
            result_embed.add_field(
                name="🎛️ Broadcast Admin Role",
                value="❌ Failed to create broadcast admin role",
                inline=False,
            )

        # Add hierarchy info
        if speaker_role and broadcast_admin_role:
            result_embed.add_field(
                name="📝 Next Steps",
                value="1. **Assign Roles:** Give users the appropriate roles\n"
                "2. **Test Setup:** Run `!check_setup` to verify everything\n"
                "3. **Create Section:** Run `!start_broadcast 'Test Room'` or `!start_broadcast 'Test Room' 3`\n"
                "4. **Learn More:** Run `!how_it_works` for usage guide",
                inline=False,
            )
        else:
            result_embed.add_field(
                name="⚠️ Issues Found",
                value="Some roles could not be created. Check bot permissions with `!check_permissions`",
                inline=False,
            )
            result_embed.color = discord.Color.orange()

        return result_embed

    def _check_bot_permissions(self, ctx: commands.Context) -> list:
        """Check bot permissions and return status list."""
        bot_member = ctx.guild.me
        perms = bot_member.guild_permissions
        has_administrator = perms.administrator

        permission_status = []
        if has_administrator:
            permission_status.append("✅ Administrator (Full Access)")
        else:
            permission_status += [
                f"{'✅' if perms.manage_channels else '❌'} Manage Channels",
                f"{'✅' if perms.manage_roles else '❌'} Manage Roles",
                f"{'✅' if perms.connect else '❌'} Connect (Voice)",
                f"{'✅' if perms.speak else '❌'} Speak (Voice)",
            ]
        return permission_status

    def _check_required_roles(self, ctx: commands.Context) -> list:
        """Check required roles and return status list."""
        speaker_role = discord.utils.get(ctx.guild.roles, name="Speaker")
        broadcast_admin_role = discord.utils.get(
            ctx.guild.roles, name="Broadcast Admin"
        )

        role_status = []
        if speaker_role:
            role_status.append(
                f"✅ Speaker Role ({sum(1 for m in ctx.guild.members if speaker_role in m.roles)} members)"
            )
        else:
            role_status.append("❌ Speaker Role (Missing)")
        if broadcast_admin_role:
            role_status.append(
                f"✅ Broadcast Admin Role ({sum(1 for m in ctx.guild.members if broadcast_admin_role in m.roles)} members)"
            )
        else:
            role_status.append("❌ Broadcast Admin Role (Missing)")
        return role_status

    def _check_active_section(self, ctx: commands.Context) -> str:
        """Check for active broadcast section."""
        has_active_section = (
            ctx.guild.id in self.audio_router.section_manager.active_sections
        )
        if has_active_section:
            section = self.audio_router.section_manager.active_sections[ctx.guild.id]
            return (
                f"✅ **{section.section_name}**\n"
                f"Status: {'🟢 Broadcasting' if section.is_active else '🔴 Stopped'}\n"
                f"Listener Channels: {len(section.listener_channel_ids)}"
            )
        else:
            return "❌ No active broadcast section found"

    def _identify_setup_issues(self, ctx: commands.Context, role_status: list) -> list:
        """Identify setup issues."""
        issues = []
        bot_member = ctx.guild.me
        perms = bot_member.guild_permissions

        if not perms.administrator and (
            not perms.manage_channels or not perms.manage_roles
        ):
            issues.append("• Bot lacks required permissions")
        if not any(
            "Speaker Role" in status and "✅" in status for status in role_status
        ):
            issues.append("• Required roles are missing")
        if not perms.connect or not perms.speak:
            issues.append("• Bot cannot access voice channels")
        return issues

    def _add_issues_to_embed(self, embed: discord.Embed, issues: list) -> discord.Embed:
        """Add issues and fixes to embed."""
        embed.add_field(name="⚠️ Issues Found", value="\n".join(issues), inline=False)
        embed.add_field(
            name="🔧 How to Fix",
            value="• Run `!check_permissions` for detailed permission analysis\n"
            "• Run `!setup_roles` to create missing roles\n"
            "• Contact your server administrator if permissions are missing",
            inline=False,
        )
        embed.color = discord.Color.orange()
        return embed

    def _add_success_to_embed(self, embed: discord.Embed) -> discord.Embed:
        """Add success message to embed."""
        embed.add_field(
            name="✅ Setup Status",
            value="Your server is properly configured! You can:\n"
            "• Run `!start_broadcast 'Name'` or `!start_broadcast 'Name' N` to create and start a broadcast section\n"
            "• Run `!how_it_works` to learn how to use the system",
            inline=False,
        )
        embed.color = discord.Color.green()
        return embed

    def _get_permission_checks(self) -> list:
        """Get list of permission checks."""
        return [
            (
                "Manage Channels",
                "manage_channels",
                "Required to create and manage voice channels",
            ),
            ("Manage Roles", "manage_roles", "Required to create and manage roles"),
            ("Connect", "connect", "Required to join voice channels"),
            ("Speak", "speak", "Required to play audio in voice channels"),
            ("Send Messages", "send_messages", "Required to send command responses"),
            (
                "Read Message History",
                "read_message_history",
                "Required to read command messages",
            ),
            ("Embed Links", "embed_links", "Required to send rich embeds"),
            ("Administrator", "administrator", "Full access to all features"),
        ]

    def _analyze_permissions(self, perms, permissions) -> tuple:
        """Analyze bot permissions."""
        permission_status = []
        missing_permissions = []
        for perm_name, perm_attr, description in permissions:
            has_perm = getattr(perms, perm_attr, False)
            status = "✅" if has_perm else "❌"
            permission_status.append(f"{status} **{perm_name}**")
            if not has_perm and perm_name != "Administrator":
                missing_permissions.append((perm_name, description))
        return permission_status, missing_permissions

    def _check_role_management(self, ctx: commands.Context, bot_member) -> list:
        """Check role management capabilities."""
        speaker_role = discord.utils.get(ctx.guild.roles, name="Speaker")
        broadcast_admin_role = discord.utils.get(
            ctx.guild.roles, name="Broadcast Admin"
        )

        role_management_status = []
        if speaker_role:
            can_manage_speaker = bot_member.top_role > speaker_role
            status = "✅" if can_manage_speaker else "❌"
            role_management_status.append(
                f"{status} **Speaker Role** (Position: {speaker_role.position})"
            )
        else:
            role_management_status.append("⚠️ **Speaker Role** (Not created yet)")
        if broadcast_admin_role:
            can_manage_admin = bot_member.top_role > broadcast_admin_role
            status = "✅" if can_manage_admin else "❌"
            role_management_status.append(
                f"{status} **Broadcast Admin Role** (Position: {broadcast_admin_role.position})"
            )
        else:
            role_management_status.append(
                "⚠️ **Broadcast Admin Role** (Not created yet)"
            )
        return role_management_status

    def _add_permission_fixes(
        self, embed: discord.Embed, missing_permissions: list
    ) -> discord.Embed:
        """Add permission fixes to embed."""
        embed.add_field(
            name="🔧 How to Fix Missing Permissions",
            value="**The bot needs additional permissions to function properly.**\n\n"
            "**Contact your server administrator to:**\n"
            "1. Go to **Server Settings** → **Roles**\n"
            "2. Find the bot's role (usually named after the bot)\n"
            "3. Enable the missing permissions:\n"
            + "\n".join(
                [f"   • **{perm}** - {desc}" for perm, desc in missing_permissions]
            )
            + "\n4. **Move the bot's role higher** in the role list (above other roles)\n"
            "5. **Save changes** and try again",
            inline=False,
        )
        embed.color = discord.Color.orange()
        return embed

    def _add_permission_success(self, embed: discord.Embed) -> discord.Embed:
        """Add permission success message to embed."""
        embed.add_field(
            name="✅ Permission Status",
            value="**All required permissions are present!**\n"
            "The bot should work correctly. If you're still having issues:\n"
            "• Run `!setup_roles` to create required roles\n"
            "• Run `!check_setup` to verify everything is working",
            inline=False,
        )
        embed.color = discord.Color.green()
        return embed

    def _add_hierarchy_warning(self, embed: discord.Embed) -> discord.Embed:
        """Add role hierarchy warning to embed."""
        embed.add_field(
            name="⚠️ Role Hierarchy Issue",
            value="**The bot's role is positioned too low in the hierarchy.**\n"
            "This can cause permission issues even if permissions are granted.\n\n"
            "**Fix:** Move the bot's role higher in the role list (closer to the top)",
            inline=False,
        )
        return embed

    def _add_speaker_role_info(
        self,
        embed: discord.Embed,
        speaker_role: Optional[discord.Role],
        guild: discord.Guild,
    ) -> discord.Embed:
        """Add speaker role information to embed."""
        if speaker_role:
            speaker_members = [
                member for member in guild.members if speaker_role in member.roles
            ]
            embed.add_field(
                name="🎤 Speaker Role",
                value=f"**Role:** {speaker_role.mention}\n"
                f"**Purpose:** Required to join speaker channels\n"
                f"**Members:** {len(speaker_members)} users\n"
                f"**Position:** {speaker_role.position}",
                inline=False,
            )
        else:
            embed.add_field(
                name="🎤 Speaker Role",
                value="**Status:** ❌ Not created\n"
                "**Purpose:** Required to join speaker channels\n"
                "**Action:** Run `!setup_roles` to create this role",
                inline=False,
            )
        return embed

    def _add_broadcast_admin_role_info(
        self,
        embed: discord.Embed,
        broadcast_admin_role: Optional[discord.Role],
        guild: discord.Guild,
    ) -> discord.Embed:
        """Add broadcast admin role information to embed."""
        if broadcast_admin_role:
            admin_members = [
                member
                for member in guild.members
                if broadcast_admin_role in member.roles
            ]
            embed.add_field(
                name="🎛️ Broadcast Admin Role",
                value=f"**Role:** {broadcast_admin_role.mention}\n"
                f"**Purpose:** Required to use bot commands\n"
                f"**Members:** {len(admin_members)} users\n"
                f"**Position:** {broadcast_admin_role.position}",
                inline=False,
            )
        else:
            embed.add_field(
                name="🎛️ Broadcast Admin Role",
                value="**Status:** ❌ Not created\n"
                "**Purpose:** Required to use bot commands\n"
                "**Action:** Run `!setup_roles` to create this role",
                inline=False,
            )
        return embed

    def _add_role_system_explanation(self, embed: discord.Embed) -> discord.Embed:
        """Add role system explanation to embed."""
        embed.add_field(
            name="🔧 How the Role System Works",
            value="• **🎤 Speaker Role:** Users with this role can join speaker channels to broadcast audio\n"
            "• **🎛️ Broadcast Admin Role:** Users with this role can use bot commands to control broadcasts\n"
            "• **👑 Server Administrators:** Can always use all commands and join any channel\n"
            "• **👥 Everyone Else:** Can join listener channels freely (no role required)\n"
            "• **🔒 Category Visibility:** Use `--role 'RoleName'` to restrict who can see broadcast categories",
            inline=False,
        )
        return embed

    def _add_usage_examples(self, embed: discord.Embed) -> discord.Embed:
        """Add usage examples to embed."""
        embed.add_field(
            name="📝 Usage Examples",
            value="• **For a presentation:** Give Speaker role to the presenter, everyone else joins listener channels\n"
            "• **For a meeting:** Give Broadcast Admin role to meeting organizers, Speaker role to speakers\n"
            "• **For an event:** Create multiple broadcast sections, assign roles as needed\n"
            "• **For VIP content:** Use `!start_broadcast 'VIP Session' 5 --role 'Premium Members'`\n"
            "• **For public events:** Use `!start_broadcast 'Public Event' 10` (visible to everyone)",
            inline=False,
        )
        return embed

    def _add_setup_next_steps(self, embed: discord.Embed) -> discord.Embed:
        """Add setup next steps to embed."""
        embed.add_field(
            name="🚀 Next Steps",
            value="1. Run `!setup_roles` to create the required roles\n"
            "2. Assign roles to users as needed\n"
            "3. Run `!start_broadcast 'Name'` or `!start_broadcast 'Name' N` to create and start your first broadcast section",
            inline=False,
        )
        embed.color = discord.Color.orange()
        return embed

    def _add_ready_to_use(self, embed: discord.Embed) -> discord.Embed:
        """Add ready to use message to embed."""
        embed.add_field(
            name="✅ Ready to Use",
            value="All required roles are set up! You can now:\n"
            "• Assign roles to users\n"
            "• Create and start broadcast sections with `!start_broadcast 'Name'` or `!start_broadcast 'Name' N`\n"
            "• Stop and clean up with `!stop_broadcast`",
            inline=False,
        )
        embed.color = discord.Color.green()
        return embed
