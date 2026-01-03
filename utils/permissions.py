import os
from typing import Optional
import discord

STAFF_ROLE = os.getenv('STAFF_ROLE', 'Staff')
ADMIN_ROLE = os.getenv('ADMIN_ROLE', 'Admin')

class PermissionManager:
    @staticmethod
    async def check_permission(interaction: discord.Interaction, required_role: str) -> bool:
        """Check if user has required permissions"""
        member = interaction.user
        
        if required_role == 'user':
            return True
        
        # Check if user has admin permissions in Discord
        if member.guild_permissions.administrator:
            return True
        
        if required_role == 'staff':
            # Check role names
            staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE)
            admin_role = discord.utils.get(interaction.guild.roles, name=ADMIN_ROLE)
            
            if staff_role and staff_role in member.roles:
                return True
            if admin_role and admin_role in member.roles:
                return True
            if member.guild_permissions.manage_guild:
                return True
        
        if required_role == 'admin':
            # Check admin role
            admin_role = discord.utils.get(interaction.guild.roles, name=ADMIN_ROLE)
            if admin_role and admin_role in member.roles:
                return True
            if member.guild_permissions.administrator:
                return True
        
        return False
    
    @staticmethod
    async def enforce_permission(interaction: discord.Interaction, required_role: str) -> bool:
        """Enforce permission check and respond if failed"""
        has_perm = await PermissionManager.check_permission(interaction, required_role)
        if not has_perm:
            if required_role == 'staff':
                role_name = STAFF_ROLE
            elif required_role == 'admin':
                role_name = ADMIN_ROLE
            else:
                role_name = required_role
                
            await interaction.response.send_message(
                f"❌ You need the `{role_name}` role to use this command.",
                ephemeral=True
            )
        return has_perm
