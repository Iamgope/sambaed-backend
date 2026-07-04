"""
Usage:
    python manage.py seed_data          # seed everything
    python manage.py seed_data --flush  # wipe existing seed data first
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from debate.constants import DebateStatus, ProOrCon, RoundType
from debate.models import Category, Debate, Judgement, Message, Round, Topic
from users.models import UserProfile


CATEGORIES = [
    {
        "name": "Politics",
        "description": "Democracy, policy, governance, and the power of institutions.",
        "topics": [
            ("Should voting be mandatory?",
             "Many democracies struggle with low turnout. Compulsory voting is used in over 20 countries."),
            ("Is electoral college better than popular vote?",
             "The US system gives smaller states more weight. Critics argue it undermines majority rule."),
            ("Should the minimum wage be raised to ₹500/day?",
             "Rising cost of living vs. potential job losses — a classic economic tension."),
            ("Should politicians face term limits?",
             "Incumbency advantages can entrench power. Term limits force fresh leadership."),
            ("Is political correctness good for democracy?",
             "Balancing civil discourse with free speech is increasingly contested."),
        ],
    },
    {
        "name": "Sports",
        "description": "Athletes, competition, and the culture of sport.",
        "topics": [
            ("Should cricket be added to the Olympics?",
             "Cricket is the world's second-most watched sport but absent from the Olympics."),
            ("Are performance-enhancing drugs ruining sport?",
             "From EPO to gene doping — the line between training and cheating keeps moving."),
            ("Should women and men compete in the same events?",
             "Biological differences vs. the principle of equal competition."),
            ("Is money destroying football?",
             "Mega-transfers and super clubs are widening the gap between rich and poor clubs."),
            ("Should e-sports be treated as real sports?",
             "Millions watch competitive gaming. Does skill + competition = sport?"),
        ],
    },
    {
        "name": "Culture",
        "description": "Art, media, identity, and what we value as a society.",
        "topics": [
            ("Are translations betraying the originals?",
             "Every translated word is an interpretation. Does this distort the author's intent?"),
            ("Do we glorify violence in cinema too much?",
             "From Tarantino to war films — how much screen violence is too much?"),
            ("Should art with a problematic creator still be celebrated?",
             "Separating art from artist: Wagner, Picasso, Woody Allen."),
            ("Is social media destroying youth culture?",
             "Attention spans, mental health, and the TikTok generation."),
            ("Should cultural appropriation be criminalised?",
             "Borrowing vs. stealing — when does appreciation become exploitation?"),
        ],
    },
    {
        "name": "Technology",
        "description": "AI, privacy, disruption, and the digital future.",
        "topics": [
            ("Should AI-generated content require disclosure?",
             "Deepfakes and AI writing are indistinguishable from human work. Does the audience have a right to know?"),
            ("Is social media more harmful than beneficial?",
             "Connection and information vs. addiction, misinformation, and polarisation."),
            ("Should big tech companies be broken up?",
             "Google, Meta, Amazon — monopoly power in the 21st century."),
            ("Will AI take more jobs than it creates?",
             "Automation has always disrupted labour. This time may be different."),
            ("Should there be a universal right to internet access?",
             "3 billion people remain offline. Is connectivity now a human right?"),
        ],
    },
    {
        "name": "Philosophy",
        "description": "Ethics, consciousness, meaning, and how we should live.",
        "topics": [
            ("Is free will an illusion?",
             "Neuroscience suggests decisions are made before we're conscious of them."),
            ("Should euthanasia be a universal right?",
             "Autonomy over one's death vs. the sanctity of life and risk of abuse."),
            ("Do we have moral obligations to future generations?",
             "Climate change forces us to consider people who don't yet exist."),
            ("Is morality objective or subjective?",
             "Moral realism vs. relativism — the oldest debate in ethics."),
            ("Should secular societies adopt a shared ethical framework?",
             "Without religion, what grounds our moral consensus?"),
        ],
    },
]

SAMPLE_USERS = [
    {"username": "zara_k",    "first_name": "Zara",   "last_name": "Khan",    "elo": 1840, "wins": 31, "debates": 45, "streak": 4,  "bio": "Debate coach by day. Overthinker always."},
    {"username": "dev_p",     "first_name": "Dev",    "last_name": "Patel",   "elo": 1620, "wins": 19, "debates": 33, "streak": 2,  "bio": "Sports and policy nerd. BITS Pilani '22."},
    {"username": "aisha_n",   "first_name": "Aisha",  "last_name": "Nair",    "elo": 2105, "wins": 58, "debates": 71, "streak": 9,  "bio": "Reading more books than I can finish."},
    {"username": "kabir_s",   "first_name": "Kabir",  "last_name": "Singh",   "elo": 1380, "wins": 11, "debates": 24, "streak": 0,  "bio": "Law student. Probably biased."},
    {"username": "priya_sh",  "first_name": "Priya",  "last_name": "Sharma",  "elo": 1755, "wins": 27, "debates": 39, "streak": 3,  "bio": "Philosophy + tech. Ask me about consciousness."},
]


class Command(BaseCommand):
    help = "Seed the database with sample categories, topics, users, and debates"

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete existing seed data before seeding")

    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing existing seed data…")
            Debate.objects.all().delete()
            Topic.objects.all().delete()
            Category.objects.all().delete()
            User.objects.filter(username__in=[u["username"] for u in SAMPLE_USERS]).delete()
            self.stdout.write(self.style.WARNING("Flushed."))

        # ── Categories & Topics ───────────────────────────────────────────────
        self.stdout.write("Seeding categories and topics…")
        cat_objs = {}
        topic_objs = []
        for cat_data in CATEGORIES:
            cat, _ = Category.objects.get_or_create(
                name=cat_data["name"],
                defaults={"description": cat_data["description"]},
            )
            cat_objs[cat_data["name"]] = cat
            for i, (title, desc) in enumerate(cat_data["topics"]):
                topic, _ = Topic.objects.get_or_create(
                    title=title,
                    defaults={"description": desc, "category": cat, "priority": i},
                )
                topic_objs.append(topic)
        self.stdout.write(self.style.SUCCESS(f"  {len(cat_objs)} categories, {len(topic_objs)} topics"))

        # ── Sample users & profiles ───────────────────────────────────────────
        self.stdout.write("Seeding sample users…")
        sample_user_objs = []
        for u in SAMPLE_USERS:
            user, created = User.objects.get_or_create(
                username=u["username"],
                defaults={
                    "first_name": u["first_name"],
                    "last_name":  u["last_name"],
                    "email": f"{u['username']}@samvaad.app",
                },
            )
            if created:
                user.set_password("sample123")
                user.save()
            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "elo_rating":    u["elo"],
                    "wins":          u["wins"],
                    "losses":        u["debates"] - u["wins"],
                    "total_debates": u["debates"],
                    "streak":        u["streak"],
                    "bio":           u["bio"],
                },
            )
            sample_user_objs.append(user)
        self.stdout.write(self.style.SUCCESS(f"  {len(sample_user_objs)} sample users"))

        # ── testuser profile ──────────────────────────────────────────────────
        try:
            testuser = User.objects.get(username="testuser")
            UserProfile.objects.update_or_create(
                user=testuser,
                defaults={
                    "elo_rating": 2047, "wins": 94, "losses": 48,
                    "total_debates": 142, "streak": 6,
                    "bio": "Reading more than I write. Trying to argue better.",
                },
            )
            self.stdout.write(self.style.SUCCESS("  testuser profile updated"))
        except User.DoesNotExist:
            self.stdout.write(self.style.WARNING("  testuser not found — skipping profile"))

        # ── Completed debates ─────────────────────────────────────────────────
        self.stdout.write("Seeding sample debates…")
        if not User.objects.filter(username="testuser").exists():
            self.stdout.write(self.style.WARNING("  testuser missing — skipping debates"))
            return

        testuser = User.objects.get(username="testuser")
        debate_specs = [
            # (topic_title, pro_user, con_user, winner_is_pro, days_ago)
            ("Should voting be mandatory?",             testuser,         sample_user_objs[0], True,  1),
            ("Should cricket be added to the Olympics?",sample_user_objs[1], testuser,        False, 2),
            ("Are translations betraying the originals?",testuser,        sample_user_objs[2], False, 3),
            ("Is free will an illusion?",               sample_user_objs[3], testuser,        False, 5),
            ("Do we glorify violence in cinema too much?",testuser,       sample_user_objs[4], True,  7),
            ("Will AI take more jobs than it creates?", sample_user_objs[0], testuser,        False, 9),
            ("Is morality objective or subjective?",    testuser,         sample_user_objs[2], True,  12),
        ]

        created_debates = 0
        for title, pro, con, pro_wins, days_ago in debate_specs:
            try:
                topic = Topic.objects.get(title=title)
            except Topic.DoesNotExist:
                continue

            completed_at = timezone.now() - timedelta(days=days_ago)

            debate = Debate.objects.create(
                topic=topic,
                user_pro=pro,
                user_con=con,
                winner=pro if pro_wins else con,
                status=DebateStatus.COMPLETED,
                completed_at=completed_at,
            )

            # Rounds
            round_types = [RoundType.OPENING, RoundType.REBUTTAL, RoundType.CLOSING]
            for order, rtype in enumerate(round_types, 1):
                t = completed_at - timedelta(minutes=(3 - order) * 8)
                round_obj = Round.objects.create(
                    debate=debate, round_type=rtype, order=order,
                    started_at=t, ended_at=t + timedelta(minutes=6),
                    current_speaker=pro if order % 2 == 1 else con,
                    turn_started_at=t,
                )
                Message.objects.create(
                    debate=debate, round=round_obj, user=pro,
                    content=_pro_message(rtype, topic.title),
                )
                Message.objects.create(
                    debate=debate, round=round_obj, user=con,
                    content=_con_message(rtype, topic.title),
                )

            # Judgement
            if pro_wins:
                arg_pro, arg_con = 8.2, 6.4
                reb_pro, reb_con = 7.8, 6.1
                cla_pro, cla_con = 8.5, 7.0
                per_pro, per_con = 8.0, 6.8
            else:
                arg_pro, arg_con = 6.1, 8.5
                reb_pro, reb_con = 5.9, 7.9
                cla_pro, cla_con = 7.2, 8.3
                per_pro, per_con = 6.5, 8.1

            Judgement.objects.create(
                debate=debate,
                winner=pro if pro_wins else con,
                argument_score_pro=arg_pro, rebuttal_score_pro=reb_pro,
                clarity_score_pro=cla_pro,  persuasion_score_pro=per_pro,
                argument_score_con=arg_con, rebuttal_score_con=reb_con,
                clarity_score_con=cla_con,  persuasion_score_con=per_con,
                reasoning=f"{'PRO' if pro_wins else 'CON'} presented stronger evidence and clearer structure throughout.",
                strongest_moment=f"The {'PRO' if pro_wins else 'CON'} rebuttal in round 2 was decisive.",
                coaching_tip_pro="Work on anticipating counterarguments earlier.",
                coaching_tip_con="Use more concrete examples to back your claims.",
            )
            created_debates += 1

        self.stdout.write(self.style.SUCCESS(f"  {created_debates} debates with rounds, messages, and judgements"))
        self.stdout.write(self.style.SUCCESS("✓ Seed complete"))


def _pro_message(round_type: str, topic: str) -> str:
    if round_type == RoundType.OPENING:
        return f"The case for this is straightforward: '{topic}' demands we consider the evidence carefully. The data overwhelmingly supports the affirmative position."
    if round_type == RoundType.REBUTTAL:
        return "My opponent raises valid concerns, but fails to address the core structural argument. The counterexample they cite is an outlier, not the norm."
    return "In closing: the affirmative position rests on stronger empirical foundations, clearer logical structure, and a more realistic assessment of outcomes. I urge a PRO verdict."


def _con_message(round_type: str, topic: str) -> str:
    if round_type == RoundType.OPENING:
        return f"The opposition to '{topic}' stems from practical reality. What sounds compelling in theory consistently fails when implemented — history is clear on this."
    if round_type == RoundType.REBUTTAL:
        return "The PRO side cites aggregate trends while ignoring distributional effects. The communities most affected tell a very different story than the statistics suggest."
    return "In summary: the CON position acknowledges complexity rather than oversimplifying it. Real progress requires honest accounting of trade-offs, not wishful thinking."
