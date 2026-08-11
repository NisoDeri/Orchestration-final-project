from __future__ import annotations

import argparse
import json
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def _subject(result: dict) -> str:
    game_id = str(result["game_id"])
    final = result["final_result"]
    totals = final["total_score"]
    verdict = "series_tie" if final.get("series_tie") else f"winner={final.get('winner_group')}"
    score = " ".join(f"{gid}:{totals[gid]}" for gid in sorted(totals))
    return f"P2P league SERIES result - {game_id} - {verdict} - {score}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", default="logs/nis-yar1/result_anrbj666-vs-nis-yar1.json")
    parser.add_argument("--smtp", default="secrets/smtp.json")
    parser.add_argument("--from-addr", default="yardentziar@gmail.com")
    parser.add_argument("--to", action="append", default=[])
    args = parser.parse_args()

    result_path = Path(args.result)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    creds = json.loads(Path(args.smtp).read_text(encoding="utf-8-sig"))
    recipients = args.to or ["alonisrael.engel@gmail.com", "yardentziar@gmail.com"]
    body = json.dumps(result, ensure_ascii=False, indent=2)
    game_id = str(result["game_id"])

    msg = MIMEMultipart()
    msg["Subject"] = _subject(result)
    msg["From"] = args.from_addr
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain", "utf-8"))
    attachment = MIMEApplication(body.encode("utf-8"), _subtype="json")
    attachment.add_header("Content-Disposition", "attachment",
                          filename=f"result_{game_id}.json")
    msg.attach(attachment)

    with smtplib.SMTP(creds.get("host", "smtp.gmail.com"),
                      int(creds.get("port", 587)), timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(creds["user"], creds["password"])
        smtp.sendmail(args.from_addr, recipients, msg.as_string())

    print("sent")
    print(msg["Subject"])
    print(msg["To"])
    print(f"result_{game_id}.json")


if __name__ == "__main__":
    main()
