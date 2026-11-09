from __future__ import annotations

import random
from datetime import timedelta

from django.utils import timezone
from django.utils.text import slugify
from taskmanager import sample_data as fake
from taskmanager.models import Member

from .models import Comment, Post, Topic

TOPICS = ["Product news", "Engineering", "Design", "Customer stories", "Guides", "Company", "Releases", "Security"]
TITLE_STARTS = ["How we", "Why we", "What we learned when we", "A closer look at how we", "Notes on how we"]
TITLE_ENDS = [
    "moved our search to Postgres",
    "redesigned the settings page",
    "cut our deploy time in half",
    "handle peak season traffic",
    "test every admin page",
    "ship features behind flags",
    "plan the quarter",
    "onboard new teammates",
    "picked our icon set",
    "rebuilt the invoice export",
    "keep our docs in sync",
    "answer support tickets faster",
]


def clear() -> None:
    Comment.objects.all().delete()
    Post.objects.all().delete()
    Topic.objects.all().delete()


def seed(rng: random.Random, scale: float) -> str:
    topics = Topic.objects.bulk_create(
        Topic(name=name, slug=slugify(name), description=fake.sentence(rng, 12)) for name in TOPICS
    )
    authors = list(Member.objects.all()[:24])
    now = timezone.now()

    posts = []
    for number in range(1, fake.scaled(160, scale) + 1):
        title = f"{rng.choice(TITLE_STARTS)} {rng.choice(TITLE_ENDS)}"
        status = rng.choices(list(Post.Status), weights=[3, 2, 14, 2])[0]
        created_at = fake.moment(rng, 900)
        posts.append(
            Post(
                title=title,
                slug=f"{slugify(title)}-{number}",
                author=rng.choice(authors),
                status=status,
                excerpt=fake.sentence(rng, 20),
                body=fake.paragraphs(rng, rng.randint(3, 8)),
                published_at=min(now, created_at + timedelta(days=rng.randint(0, 10)))
                if status in (Post.Status.PUBLISHED, Post.Status.ARCHIVED)
                else None,
                allow_comments=rng.random() < 0.9,
                reading_minutes=rng.randint(2, 14),
                seo_title=title[:70] if rng.random() < 0.5 else "",
                created_at=created_at,
            )
        )
    Post.objects.bulk_create(posts)

    post_topic = Post.topics.through
    post_topic.objects.bulk_create(
        post_topic(post_id=post.pk, topic_id=topic.pk)
        for post in posts
        for topic in rng.sample(topics, rng.randint(1, 3))
    )

    comments = []
    for post in posts:
        if post.published_at is None or not post.allow_comments:
            continue
        for _ in range(rng.choices([0, 1, 3, 8, 20], weights=[3, 4, 4, 2, 1])[0]):
            first, last = fake.person(rng)
            spam = rng.random() < 0.06
            comments.append(
                Comment(
                    post=post,
                    name=f"{first} {last}",
                    email=f"{first}.{last}@mail.example".lower(),
                    body=fake.sentence(rng, rng.randint(6, 40)),
                    is_spam=spam,
                    is_approved=not spam and rng.random() < 0.85,
                    ip_address=f"{rng.randint(11, 220)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}",
                    created_at=min(now, post.published_at + timedelta(hours=rng.randint(1, 900))),
                )
            )
    Comment.objects.bulk_create(comments)
    return f"{len(topics)} topics, {len(posts)} posts, {len(comments)} comments"
