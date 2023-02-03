import re
import requests
from bs4 import BeautifulSoup, Tag
from enum import Enum
from typing import Union

Team = dict[str, Union[int, str]]
Player = dict[str, Union[int, str]]
Card = dict[str, Union[int, Player, str]]
Subs = dict[str, Union[int, Player]]

LEAGUE_SELECTOR = "#mcd > table:nth-child(10) > tr > td > table.tbl > tr:nth-child(1) > td > table > tr > td:nth-child(1) > h2"
DATE_SELECTOR = "#mcd > table:nth-child(10) > tr > td > table.tbl > tr:nth-child(1) > td > table > tr > td:nth-child(2) > h3"
ATTENDANCE_SELECTOR = "#mcd > table:nth-child(10) > tr > td > table.tbl > tr:nth-child(2) > td > table > tr > td"
TEAM_SELECTOR = "#mcd > table:nth-child(10) > tr > td > table.tbl > tr:nth-child(3) > td > table > tr > td:nth-child({}) > h2 > a"
SCORES_SELECTOR = "#mcd > table:nth-child(10) > tr > td > table.tbl > tr:nth-child(3) > td > table > tr > td:nth-child(2) > h1"
STARTING_SELECTOR = "#mcd > table:nth-child(10) > tr > td > table:nth-child(2) > tr:nth-child(3) > td > table > tr > td:nth-child({}) > table > tr"
SUBSTITUTES_SELETOR = "#mcd > table:nth-child(10) > tr:nth-child(3) > td > table > tr > td:nth-child({}) > table > tr"
EVENT_SELECTOR = "#mcd > table:nth-child(10) > tr:nth-child({}) > td > table > tr > td:nth-child({}) > a"


class HomeAway(Enum):
    HOME = 1
    AWAY = 2


class Event(Enum):
    YELLOW_CARD = 7
    RED_CARD = 9
    SUBSTITUTION = 11


class ResultParser:
    def __init__(self, html: str) -> None:
        self.html = html
        self.soup = BeautifulSoup(self.html, "html.parser")

    def parse_league_name(self) -> str:
        return self.soup.select_one(LEAGUE_SELECTOR).text

    def parse_date(self) -> str:
        return self.soup.select_one(DATE_SELECTOR).text

    def parse_attendance(self) -> int:
        attendance = (
            self.soup.select_one(ATTENDANCE_SELECTOR).text.split(":")[1].strip()
        )
        if attendance.isnumeric():
            return int(attendance)

    def parse_team(self, team: HomeAway) -> Team:
        team = self.soup.select_one(TEAM_SELECTOR.format(team.value * 2 - 1))
        return {"id": int(team["href"].split("/")[2]), "name": team.text}

    def parse_scores(self) -> dict[str, int]:
        scores = self.soup.select_one(SCORES_SELECTOR).text.split(":")
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
        players = self.soup.select(STARTING_SELECTOR.format(team.value))
        return [
            self.parse_player_with_number(player, team)
            for player in players
            if player.text.strip()
        ]

    def parse_substitutes(self, team: HomeAway) -> list[Player]:
        players = self.soup.select(SUBSTITUTES_SELETOR.format(team.value))
        return [
            self.parse_player_with_number(player, team)
            for player in players
            if player.text.strip()
        ]

    @staticmethod
    def parse_minute(minute: str) -> int:
        if minutes := re.search(r"(\d+)", minute):
            return int(minutes[0])

    def parse_cards(self, card_type: Event, team: HomeAway) -> list[Card]:
        cards = self.soup.select(EVENT_SELECTOR.format(card_type.value, team.value))
        return [
            {
                "event": " ".join(card_type.name.split("_")).title(),
                "team": team.name.title(),
                "player": self.parse_player(card),
                "minute": self.parse_minute(card.next_sibling),
            }
            for card in cards
        ]

    def parse_substitutions(self, team: HomeAway) -> list[Subs]:
        players = self.soup.select(
            EVENT_SELECTOR.format(Event.SUBSTITUTION.value, team.value)
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
            "home": self.parse_team(HomeAway.HOME),
            "away": self.parse_team(HomeAway.AWAY),
            "scores": self.parse_scores(),
            "attendance": self.parse_attendance(),
            "lineup": {
                "home": {
                    "starting": self.parse_startings(HomeAway.HOME),
                    "substitutes": self.parse_substitutes(HomeAway.HOME),
                },
                "away": {
                    "starting": self.parse_startings(HomeAway.AWAY),
                    "substitutes": self.parse_substitutes(HomeAway.AWAY),
                },
            },
            "events": sorted(
                self.parse_goals(HomeAway.HOME)
                + self.parse_goals(HomeAway.AWAY)
                + self.parse_cards(Event.YELLOW_CARD, HomeAway.HOME)
                + self.parse_cards(Event.YELLOW_CARD, HomeAway.AWAY)
                + self.parse_cards(Event.RED_CARD, HomeAway.HOME)
                + self.parse_cards(Event.RED_CARD, HomeAway.AWAY),
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


print(get_result(36789))
