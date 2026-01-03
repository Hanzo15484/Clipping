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
        
        if required_role == 'staff':
            return any(role.name in [STAFF_ROLE, ADMIN_ROLE] for role in member.roles)
        
        if required_role == 'admin':
            return any(role.name == ADMIN_ROLE for role in member.roles)
        
        return False
    
    @staticmethod
    async def enforce_permission(interaction: discord.Interaction, required_role: str) -> bool:
        """Enforce permission check and respond if failed"""
        has_perm = await PermissionManager.check_permission(interaction, required_role)
        if not has_perm:
            await interaction.response.send_message(
                "❌ You do not have permission to use this command.",
                ephemeral=True
            )
        return has_perm
