import re
import requests
from bs4 import BeautifulSoup, Tag
from typing import Union

Team = dict[str, Union[int, str]]
Player = dict[str, Union[int, str]]
Card = dict[str, Union[int, Player, str]]
Subs = dict[str, Union[int, Player]]


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
        return int(
            self.soup.select_one(
                "#mcd > table:nth-child(10) > tr > td > table.tbl > tr:nth-child(2) > td > table > tr > td"
            )
            .text.split(":")[1]
            .strip()
        )

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
        return {
            "home": int(scores[0]),
            "away": int(scores[1]),
        }

    @staticmethod
    def parse_player(player: Tag) -> Player:
        return {
            "id": int(player["href"].split("=")[-1]),
            "name": player.text,
        }

    def parse_home_player_with_number(self, player: Tag) -> Player:
        return {
            "number": int(player.select_one("td:nth-of-type(1)").text),
            **self.parse_player(player.select_one("td:nth-of-type(2) > a")),
        }

    def parse_away_player_with_number(self, player: Tag) -> Player:
        return {
            "number": int(player.select_one("td:nth-of-type(2)").text),
            **self.parse_player(player.select_one("td:nth-of-type(1) > a")),
        }

    def parse_home_startings(self) -> list[Player]:
        players = self.soup.select(
            "#mcd > table:nth-child(10) > tr > td > table:nth-child(2) > tr:nth-child(3) > td > table > tr > td:nth-child(1) > table > tr"
        )
        return [
            self.parse_home_player_with_number(player)
            for player in players
            if player.text.strip()
        ]

    def parse_away_startings(self) -> list[Player]:
        players = self.soup.select(
            "#mcd > table:nth-child(10) > tr > td > table:nth-child(2) > tr:nth-child(3) > td > table > tr > td:nth-child(2) > table > tr"
        )
        return [
            self.parse_away_player_with_number(player)
            for player in players
            if player.text.strip()
        ]

    def parse_home_substitutes(self) -> list[Player]:
        players = self.soup.select(
            "#mcd > table:nth-child(10) > tr:nth-child(3) > td > table > tr > td:nth-child(1) > table > tr"
        )
        return [
            self.parse_home_player_with_number(player)
            for player in players
            if player.text.strip()
        ]

    def parse_away_substitutes(self) -> list[Player]:
        players = self.soup.select(
            "#mcd > table:nth-child(10) > tr:nth-child(3) > td > table > tr > td:nth-child(2) > table > tr"
        )
        return [
            self.parse_away_player_with_number(player)
            for player in players
            if player.text.strip()
        ]

    @staticmethod
    def parse_minute(minute: str) -> int:
        minutes = re.search(r"(\d+)", minute)
        return int(minutes[0])

    def parse_card(self, card: Tag, card_type: str, team: str) -> Card:
        return {
            "event": card_type,
            "team": team,
            "player": self.parse_player(card),
            "minute": self.parse_minute(card.next_sibling),
        }

    def parse_home_yellow_cards(self) -> list[Card]:
        cards = self.soup.select(
            "#mcd > table:nth-child(10) > tr:nth-child(7) > td > table > tr > td:nth-child(1) > a"
        )
        return [self.parse_card(card, "Yellow Card", "Home") for card in cards]

    def parse_away_yellow_cards(self) -> list[Card]:
        cards = self.soup.select(
            "#mcd > table:nth-child(10) > tr:nth-child(7) > td > table > tr > td:nth-child(2) > a"
        )
        return [self.parse_card(card, "Yellow Card", "Away") for card in cards]

    def parse_home_red_cards(self) -> list[Card]:
        cards = self.soup.select(
            "#mcd > table:nth-child(10) > tr:nth-child(9) > td > table > tr > td:nth-child(1) > a"
        )
        return [self.parse_card(card, "Red Card", "Home") for card in cards]

    def parse_away_red_cards(self) -> list[Card]:
        cards = self.soup.select(
            "#mcd > table:nth-child(10) > tr:nth-child(9) > td > table > tr > td:nth-child(2) > a"
        )
        return [self.parse_card(card, "Red Card", "Away") for card in cards]

    def parse_substitutions(self, players) -> Subs:
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

    def parse_home_substitutions(self) -> list[Subs]:
        players = self.soup.select(
            "#mcd > table:nth-child(10) > tr:nth-child(11) > td > table > tr > td:nth-child(1) > a"
        )
        return self.parse_substitutions(players)

    def parse_away_substitutions(self) -> list[Subs]:
        players = self.soup.select(
            "#mcd > table:nth-child(10) > tr:nth-child(11) > td > table > tr > td:nth-child(2) > a"
        )
        return self.parse_substitutions(players)

    def parse_referee(self) -> str:
        return (
            self.soup.select_one("#mcd > table:nth-child(11) > tr:nth-child(2) > td")
            .text.strip()
            .split("\n")[0]
            .split(":")[1]
            .strip()
        )

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
                    "starting": self.parse_home_startings(),
                    "substitute": self.parse_home_substitutes(),
                },
                "away": {
                    "starting": self.parse_away_startings(),
                    "substitute": self.parse_away_substitutes(),
                },
            },
            "events": sorted(
                self.parse_home_yellow_cards()
                + self.parse_away_yellow_cards()
                + self.parse_home_red_cards()
                + self.parse_away_red_cards(),
                key=lambda e: e["minute"],
            ),
            "substitution": {
                "home": self.parse_home_substitutions(),
                "away": self.parse_away_substitutions(),
            },
            "referee": self.parse_referee(),
        }


def get_result(id):
    url = f"https://www.hkfa.com/ch/match/detail/{id}"
    response = requests.get(url)
    return {"id": id, **ResultParser(response.text).parse()}
