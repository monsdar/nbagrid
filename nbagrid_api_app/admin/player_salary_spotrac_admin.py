"""Admin views for managing player salaries from Spotrac"""

import logging

from nba_api.stats.static import players as static_players

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path

from ..models import LastUpdated, Player

logger = logging.getLogger(__name__)


class PlayerSalarySpotracAdmin(admin.ModelAdmin):
    """Admin view for managing player salaries from Spotrac"""

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("sync_salaries_from_spotrac/", self.sync_salaries_from_spotrac),
        ]
        return my_urls + urls

    def sync_salaries_from_spotrac(self, request):
        """Sync player salaries from Spotrac.com"""
        import re

        import requests
        from bs4 import BeautifulSoup

        try:
            # Fetch the Spotrac page
            url = "https://www.spotrac.com/nba/rankings/player/_/year/2024/sort/cap_base"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            # Parse the HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Find the table with player salaries
            table = soup.find("ul", {"class": "list-group"})
            if not table:
                raise Exception("Could not find salary table on Spotrac page")

            # Process each row
            updated_count = 0
            for row in table.find_all("li"):
                player_link = row.find("a", {"class": "link"})
                if not player_link:
                    continue
                player_name = player_link.text.strip()
                salary_span = row.find("span", {"class": "medium"})
                if not salary_span:
                    continue
                salary_text = salary_span.text.strip()

                # Convert salary text to integer (remove $ and commas)
                salary = int(re.sub(r"[^\d]", "", salary_text))

                # strip any left accents and special chars from the player_name
                player_name = static_players._strip_accents(player_name)
                # This is a list of players that have different names in Spotrac vs NBA.com
                # Key: Spotrac name, Value: NBA.com name
                player_mappings = {
                    "Jimmy Butler": "Jimmy Butler III",
                    "C.J. McCollum": "CJ McCollum",
                    "Nicolas Claxton": "Nic Claxton",
                    "R.J. Barrett": "RJ Barrett",
                    "Bruce Brown Jr.": "Bruce Brown",
                    "PJ Washington": "P.J. Washington",
                    "Herb Jones": "Herbert Jones",
                    "Ron Holland II": "Ronald Holland II",
                    "Kenyon Martin Jr.": "KJ Martin",
                    "Jae’Sean Tate": "Jae'Sean Tate",  # NOTE: keep the apostrophe ’, as this is how it's spelled in Spotrac
                    "Cameron Thomas": "Cam Thomas",
                    "Sviatoslav Mykhailiuk": "Svi Mykhailiuk",
                    "Vincent Williams Jr.": "Vince Williams Jr.",
                    "G.G. Jackson": "GG Jackson",
                    "Cameron Christie": "Cam Christie",
                    "Brandon Boston Jr": "Brandon Boston",
                    "Jeenathan Williams": "Nate Williams",
                    "Kevin Knox": "Kevin Knox II",
                    "Mohamed Bamba": "Mo Bamba",
                    "Kevon Harris": "Kevon Harris",
                    "Terence Davis": "Terence Davis",
                    "J.D. Davison": "JD Davison",
                }
                if player_name in player_mappings:
                    player_name = player_mappings[player_name]

                # Find matching player(s) and update salary
                players = Player.objects.filter(name__iexact=player_name)
                if players.exists():
                    for player in players:
                        player.base_salary = salary
                        player.save()
                        updated_count += 1
                        # logger.info(f"Updated salary for {player.name}: ${salary:,}")
                else:
                    logger.warning(f"No player found for {player_name}")

            # Record the update
            LastUpdated.update_timestamp(
                data_type="player_salaries_update",
                updated_by=f"Admin ({request.user.username})",
                notes=f"Updated salaries for {updated_count} players from Spotrac",
            )

            self.message_user(request, f"Successfully updated salaries for {updated_count} players", level="success")

        except Exception as e:
            logger.error(f"Error syncing salaries: {str(e)}")
            self.message_user(request, f"Error syncing salaries: {str(e)}", level="error")

        return HttpResponseRedirect("../")
