from django.core.management.base import BaseCommand

from news.services import fetch_world_events, generate_perspectives_for_events


class Command(BaseCommand):
    help = "Fetch events and generate steelmanned debate perspectives via LLM."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument(
            "--time",
            default="week",
            choices=["week", "month", "year", "all"],
        )

    def handle(self, *args, **opts):
        events = fetch_world_events(limit=opts["limit"], time_filter=opts["time"])
        stats = generate_perspectives_for_events(events=events)
        self.stdout.write(repr(stats))
