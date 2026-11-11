"""Synthetic cross-database seeder for PostgreSQL (finance_db) and MySQL (engagement_db).

Populates 50 interconnected synthetic customers linked via `email` / `customer_email`
for testing Cross-Cloud Conversational Analytics. All connection parameters are read
from environment variables (no hardcoded hosts or credentials).
"""

from datetime import datetime, timedelta
import os
import random

import psycopg2
import pymysql


def seed() -> None:
    pg_conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DB", "finance_db"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    )
    my_conn = pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        database=os.environ.get("MYSQL_DB", "engagement_db"),
        user=os.environ.get("MYSQL_USER", "admin"),
        password=os.environ["MYSQL_PASSWORD"],
        connect_timeout=5,
    )

    try:
        pg_cur = pg_conn.cursor()
        my_cur = my_conn.cursor()

        pg_cur.execute("TRUNCATE customers, accounts, transactions RESTART IDENTITY;")
        my_cur.execute("TRUNCATE support_tickets;")
        my_cur.execute("TRUNCATE campaign_responses;")

        first_names = [
            "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael",
            "Linda", "William", "Elizabeth", "David", "Barbara", "Richard", "Susan",
            "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Christopher",
            "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony", "Margaret",
            "Mark", "Sandra", "Donald", "Ashley", "Steven", "Kimberly", "Paul",
            "Emily", "Andrew", "Donna", "Joshua", "Michelle", "Kenneth", "Carol",
            "Kevin", "Amanda", "Brian", "Melissa", "George", "Deborah", "Timothy",
            "Stephanie",
        ]
        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones",
            "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
        ]
        campaigns = [
            "Summer Sale 2026", "Premium Upgrade", "New Credit Card", "Auto Loan Promo"
        ]
        responses = ["Interested", "Ignored", "Unsubscribed", "Clicked"]
        ticket_issues = [
            "Cannot login to web portal",
            "Where is my replacement card?",
            "Unexpected overdraft fee",
            "Mobile App keeps crashing",
            "Need to change my billing address",
            "Wire transfer failed",
            "Fraud alert on my checking account",
        ]

        random.seed(42)
        for idx, first in enumerate(first_names, start=1):
            name = f"{first} {random.choice(last_names)}"
            email = f"{name.lower().replace(' ', '.')}.{idx}@example.com"

            pg_cur.execute(
                "INSERT INTO customers (name, email) VALUES (%s, %s) RETURNING id;",
                (name, email),
            )
            customer_id = pg_cur.fetchone()[0]

            for _ in range(random.randint(1, 2)):
                acct_type = random.choice(["checking", "savings", "credit"])
                balance = round(
                    random.uniform(-500.0, 15000.0)
                    if acct_type != "credit"
                    else random.uniform(-5000.0, -10.0),
                    2,
                )
                pg_cur.execute(
                    "INSERT INTO accounts (customer_id, type, balance) "
                    "VALUES (%s, %s, %s) RETURNING id;",
                    (customer_id, acct_type, balance),
                )
                account_id = pg_cur.fetchone()[0]

                for _ in range(random.randint(0, 3)):
                    amount = round(random.uniform(-500.0, 500.0), 2)
                    tx_date = datetime.utcnow() - timedelta(days=random.randint(1, 30))
                    pg_cur.execute(
                        "INSERT INTO transactions (account_id, amount, date) "
                        "VALUES (%s, %s, %s);",
                        (account_id, amount, tx_date),
                    )

            if random.random() < 0.4:
                issue = random.choice(ticket_issues)
                status = random.choice(["Open", "Closed", "In Progress"])
                my_cur.execute(
                    "INSERT INTO support_tickets (customer_email, issue, status) "
                    "VALUES (%s, %s, %s);",
                    (email, issue, status),
                )

            if random.random() < 0.6:
                camp = random.choice(campaigns)
                resp = random.choice(responses)
                my_cur.execute(
                    "INSERT INTO campaign_responses (customer_email, campaign_name, response) "
                    "VALUES (%s, %s, %s);",
                    (email, camp, resp),
                )

        pg_conn.commit()
        my_conn.commit()
        print("Successfully seeded 50 interconnected customer records across PostgreSQL and MySQL.")
    finally:
        pg_conn.close()
        my_conn.close()


if __name__ == "__main__":
    seed()
