import re
import requests
from bs4 import BeautifulSoup, Tag
from enum import Enum
from typing import Union

Team = dict[str, Union[int, str]]
Player = dict[str, Union[int, str]]
Card = dict[str, Union[int, Player, str]]
Subs = dict[str, Union[int, Player]]


class HomeAway(Enum):
    HOME = 1
    AWAY = 2


class ResultParser:
    def __init__(self, html: str) -> None:
        self.html = html
        self.soup = BeautifulSoup(self.html, "html.parser")

    def parse_league_name(self) -> str:
        return self.soup.select_one(
            "#mcd > table:nth-child(10) > tr > td > table.tbl > tr:nth-child(1) > td > table > tr > td:nth-child(1) > h2"
        ).text

    def parse_date(self) -> str:
        return self.soup.select_one(
            "#mcd > table:nth-child(10) > tr > td > table.tbl > tr:nth-child(1) > td > table > tr > td:nth-child(2) > h3"
        ).text

    def parse_attendance(self) -> int:
        attendance = (
            self.soup.select_one(
                "#mcd > table:nth-child(10) > tr > td > table.tbl > tr:nth-child(2) > td > table > tr > td"
            )
            .text.split(":")[1]
            .strip()
        )
        if attendance.isnumeric():
            return int(attendance)

    @staticmethod
    def parse_team(team: Tag) -> Team:
        return {"id": int(team["href"].split("/")[2]), "name": team.text}

    def parse_home_team(self) -> Team:
        team = self.soup.select_one(
            "#mcd > table:nth-child(10) > tr > td > table.tbl > tr:nth-child(3) > td > table > tr > td:nth-child(1) > h2 > a"
        )
        return self.parse_team(team)

    def parse_away_team(self) -> Team:
        team = self.soup.select_one(
            "#mcd > table:nth-child(10) > tr > td > table.tbl > tr:nth-child(3) > td > table > tr > td:nth-child(3) > h2 > a"
        )
        return self.parse_team(team)

    def parse_scores(self) -> dict[str, int]:
        scores = self.soup.select_one(
            "#mcd > table:nth-child(10) > tr > td > table.tbl > tr:nth-child(3) > td > table > tr > td:nth-child(2) > h1"
        ).text.split(":")
        if scores != ["-", "-"]:
            return {
                "home": int(scores[0]),
                "away": int(scores[1]),
            }

    def parse_shootout_scores(self) -> dict[str, int]:
        pass

    def parser_shootout_goals(self):
        pass

    @staticmethod
    def parse_player(player: Tag) -> Player:
        if name := player.text.strip():
            return {
                "id": int(player["href"].split("=")[-1]),
                "name": name,
            }

    def parse_goals(self, team: HomeAway) -> list:
        return []

    def parse_player_with_number(self, player: Tag, team: HomeAway) -> Player:
        if team == HomeAway.HOME:
            return {
                "number": int(player.select_one("td:nth-of-type(1)").text),
                **self.parse_player(player.select_one("td:nth-of-type(2) > a")),
            }
        return {
            "number": int(player.select_one("td:nth-of-type(2)").text),
            **self.parse_player(player.select_one("td:nth-of-type(1) > a")),
        }

    def parse_startings(self, team: HomeAway) -> list[Player]:
        players = self.soup.select(
            f"#mcd > table:nth-child(10) > tr > td > table:nth-child(2) > tr:nth-child(3) > td > table > tr > td:nth-child({team.value}) > table > tr"
        )
        return [
            self.parse_player_with_number(player, team)
            for player in players
            if player.text.strip()
        ]

    def parse_substitutes(self, team: HomeAway) -> list[Player]:
        players = self.soup.select(
            f"#mcd > table:nth-child(10) > tr:nth-child(3) > td > table > tr > td:nth-child({team.value}) > table > tr"
        )
        return [
            self.parse_player_with_number(player, team)
            for player in players
            if player.text.strip()
        ]

    @staticmethod
    def parse_minute(minute: str) -> int:
        if minutes := re.search(r"(\d+)", minute):
            return int(minutes[0])

    def parse_card(self, card: Tag, card_type: str, team: str) -> Card:
        return {
            "event": card_type,
            "team": team,
            "player": self.parse_player(card),
            "minute": self.parse_minute(card.next_sibling),
        }

    def parse_yellow_cards(self, team: HomeAway) -> list[Card]:
        cards = self.soup.select(
            f"#mcd > table:nth-child(10) > tr:nth-child(7) > td > table > tr > td:nth-child({team.value}) > a"
        )
        return [self.parse_card(card, "Yellow Card", team.name) for card in cards]

    def parse_red_cards(self, team: HomeAway) -> list[Card]:
        cards = self.soup.select(
            f"#mcd > table:nth-child(10) > tr:nth-child(9) > td > table > tr > td:nth-child({team.value}) > a"
        )
        return [self.parse_card(card, "Red Card", team.name) for card in cards]

    def parse_substitutions(self, team: HomeAway) -> list[Subs]:
        players = self.soup.select(
            f"#mcd > table:nth-child(10) > tr:nth-child(11) > td > table > tr > td:nth-child({team.value}) > a"
        )
        subs = []
        for i in range(len(players) // 2):
            first: Tag = players[2 * i]
            second: Tag = players[2 * i + 1]
            subs.append(
                {
                    "in": self.parse_player(first),
                    "out": self.parse_player(second),
                    "minute": self.parse_minute(second.next_sibling),
                }
            )
        return subs

    def parse_referee(self) -> str:
        if referee := self.soup.select_one(
            "#mcd > table:nth-child(11) > tr:nth-child(2) > td"
        ):
            if ":" in referee.text:
                return referee.text.strip().split("\n")[0].split(":")[1].strip()
            elif "：" in referee.text:
                return referee.text.strip().split("\n")[0].split("：")[1].strip()

    def parse(self) -> dict:
        return {
            "league": self.parse_league_name(),
            "date": self.parse_date(),
            "home": self.parse_home_team(),
            "away": self.parse_away_team(),
            "scores": self.parse_scores(),
            "attendance": self.parse_attendance(),
            "lineup": {
                "home": {
                    "starting": self.parse_startings(HomeAway.HOME),
                    "substitute": self.parse_substitutes(HomeAway.HOME),
                },
                "away": {
                    "starting": self.parse_startings(HomeAway.AWAY),
                    "substitute": self.parse_substitutes(HomeAway.AWAY),
                },
            },
            "events": sorted(
                self.parse_goals(HomeAway.HOME)
                + self.parse_goals(HomeAway.AWAY)
                + self.parse_yellow_cards(HomeAway.HOME)
                + self.parse_yellow_cards(HomeAway.AWAY)
                + self.parse_red_cards(HomeAway.HOME)
                + self.parse_red_cards(HomeAway.AWAY),
                key=lambda e: (e["minute"] is None, e["minute"]),
            ),
            "substitutions": {
                "home": self.parse_substitutions(HomeAway.HOME),
                "away": self.parse_substitutions(HomeAway.AWAY),
            },
            "referee": self.parse_referee(),
            "shootout": {},
        }


def get_result(id):
    url = f"https://www.hkfa.com/ch/match/detail/{id}"
    response = requests.get(url)
    return {"id": id, **ResultParser(response.text).parse()}
