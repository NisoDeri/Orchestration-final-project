# Team message draft — what to share with the pod (and what NOT to)

## Decision: share interop CONFIRMATION, not our agent code

**Do NOT share `nis-yar1-cop` / `nis-yar1-thief`.** Imree shared a *conformance kit* (strategy-neutral
test vectors) — that helps everyone interoperate without revealing how anyone plays. Our repos
contain our actual competitive edges (BeliefV2 lie-detection, barrier-cage doctrine, scent-decoy,
opponent profiler). We play these exact teams in the league; publishing our strategy would be
self-defeating. Our repos go to the **grader only** (rmisegal@gmail.com), at submission. Keeping
agent code private is normal and expected in a competitive league — nobody will fault it.

**Do share:** that we independently reproduce the kit's CORE vectors byte-for-byte. That is pure
upside — it tells every opponent "you can score a clean game against nis-yar1," which is exactly
what the grade rewards (distinct clean games), and it earns collaboration goodwill. We are a second,
independent implementation that agrees on every CORE vector — a genuine conformance data point that
strengthens the kit as a shared baseline.

---

## Draft reply to the group (paste-ready)

> נעים להכיר — קבוצה **nis-yar1** (Nissim + Yarden). @Imree, תודה על ה-conformance kit, זה בדיוק
> מה שהיה חסר.
>
> הרצנו את הווקטורים מול המימוש שלנו — **אנחנו משחזרים את כל ה-CORE byte-for-byte**: commit-reveal
> (`SHA256(canonical_json(payload)|nonce)`), terms_signature, game_uid (עם sorted group-ids),
> ו-pheromone emit. שתי המלכודות שציינת עוברות אצלנו: (1) canonical JSON עם `ensure_ascii=False`
> (רמזים בעברית מקודדים כ-UTF-8 גולמי), ו-(2) מבין שלוש צורות ה-commit שבחוברת בחרנו את צורת
> ה-reference (זו שכובלת את כל הרשומה) — כמו הקיט.
>
> אנחנו מימוש עצמאי שני שמסכים על כל ה-CORE — נשמח לתרום את זה כנקודת-אימות נוספת לקיט אם עוזר.
> מוכנים ל-interop day-one.
>
> לגבי לוח זמנים: מציעים חלון warm-up בשבוע **3–9.8**, ואז משחק סָפוּר אחד מול כל זוג. נסגור זמנים
> מדויקים בהמשך. אחרי כל משחק ספור — שני הצדדים שולחים את אותו result JSON ל-
> `rmisegal+uoh26finalgame@gmail.com` ומאשרים כאן.
>
> (הקוד של הסוכנים שלנו נשאר פרטי עד ההגשה — כמקובל בליגה תחרותית — אבל כל שכבת ה-interop אצלנו
> תואמת לקיט, אז לא צפויות בעיות hash מולנו.)

---

## English version (if the group prefers English)

> Hi all — group **nis-yar1** (Nissim + Yarden). @Imree, thanks for the conformance kit, exactly what
> was missing.
>
> We ran the vectors against our implementation — **we reproduce every CORE vector byte-for-byte**:
> commit-reveal (`SHA256(canonical_json(payload)|nonce)`), terms_signature, game_uid (with sorted
> group ids), and pheromone emit. Both traps pass on our side: (1) canonical JSON with
> `ensure_ascii=False` (Hebrew hints hashed as raw UTF-8), and (2) of the three published commit
> constructions we implement the reference form (the one that binds the full record) — same as the kit.
>
> We're an independent second implementation agreeing on all CORE vectors — happy to contribute that
> as an extra conformance data point if useful. Ready for interop day-one.
>
> Scheduling: we propose a warm-up window in the week of **Aug 3–9**, then one counted game vs each
> pair. We'll pin exact times later. After each counted game both sides email the same result JSON to
> `rmisegal+uoh26finalgame@gmail.com` and confirm here.
>
> (Our agent code stays private until submission — standard for a competitive league — but our whole
> interop layer matches the kit, so no hash issues against us.)

---

## Notes for us
- Post ONLY after the user reviews. The user pastes it in the WhatsApp group.
- If asked "which codebase are you on?" answer: our own (independent), reference-wire-compatible.
- Do NOT volunteer strategy details, start-position preferences, or the rule-delta capability in
  the group chat — those are negotiated 1:1 at Step-0, per game.
