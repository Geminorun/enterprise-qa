from __future__ import annotations

from pathlib import Path
import re

from scripts.intent import Evidence


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-\u4e00-\u9fff]+")
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
ALNUM_PATTERN = re.compile(r"[A-Za-z0-9_\-]+")
STOP_TOKENS = {"怎", "么", "怎么"}


def _tokens(text: str) -> set[str]:
    raw = TOKEN_PATTERN.findall(text.lower())
    tokens: set[str] = set()
    for item in raw:
        if re.search(r"[\u4e00-\u9fff]", item):
            tokens.update(char for char in item if char not in STOP_TOKENS)
            tokens.update(token for token in _ngrams(item, 2) if token not in STOP_TOKENS)
        else:
            tokens.add(item)
    return tokens


def _ngrams(text: str, size: int) -> set[str]:
    return {text[index : index + size] for index in range(0, max(len(text) - size + 1, 0))}


def _required_alnum_terms(query: str) -> set[str]:
    return {item.lower() for item in ALNUM_PATTERN.findall(query) if len(item) >= 4}


def _query_phrases(query: str) -> set[str]:
    phrases: set[str] = set()
    for item in CHINESE_PATTERN.findall(query):
        phrases.add(item)
        phrases.update(_ngrams(item, 2))
    return {phrase for phrase in phrases if len(phrase) >= 2 and not set(phrase) & STOP_TOKENS}


def _split_markdown(path: Path) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    heading = path.stem
    current: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            if current:
                chunks.append((heading, "\n".join(current).strip()))
                current = []
            heading = line.lstrip("#").strip() or path.stem
            continue
        if line.strip():
            current.append(line)
    if current:
        chunks.append((heading, "\n".join(current).strip()))
    return chunks


def _is_meeting_note(path: Path) -> bool:
    return "meeting_notes" in path.parts


def _requires_meeting_identity_match(query: str) -> bool:
    return any(term in query for term in ("全员大会", "技术同步会", "同步会"))


def _meeting_identity_matches_query(query: str, relative: str, chunks: list[tuple[str, str]]) -> bool:
    identity = f"{relative} {' '.join(heading for heading, _ in chunks[:2])}"
    for item in CHINESE_PATTERN.findall(query):
        for size in range(min(len(item), 6), 3, -1):
            if any(ngram in identity for ngram in _ngrams(item, size)):
                return True
    return False


def search_knowledge(root_path: Path, query: str, *, limit: int = 3) -> list[Evidence]:
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    required_terms = _required_alnum_terms(query)
    query_phrases = _query_phrases(query)
    scored: list[tuple[int, str, Evidence]] = []
    for path in sorted(root_path.rglob("*.md")):
        relative = path.relative_to(root_path).as_posix()
        path_chunks = _split_markdown(path)
        is_meeting_note = _is_meeting_note(path)
        if (
            is_meeting_note
            and _requires_meeting_identity_match(query)
            and not _meeting_identity_matches_query(query, relative, path_chunks)
        ):
            continue
        local_scored: list[tuple[int, str, Evidence]] = []
        for heading, content in path_chunks:
            text = f"{relative} {heading} {content}"
            lowered_text = text.lower()
            if required_terms and not required_terms <= set(ALNUM_PATTERN.findall(lowered_text)):
                continue

            score = len(query_tokens & _tokens(text))
            score += sum(3 for phrase in query_phrases if phrase in text)
            if score >= 2:
                local_scored.append(
                    (
                        score,
                        relative,
                        Evidence(
                            kind="kb",
                            source=f"{relative} section {heading}",
                            locator=relative,
                            content=content,
                            data={"score": score},
                        ),
                    )
                )
        if is_meeting_note and local_scored:
            best_score = max(item[0] for item in local_scored)
            whole_file = path.read_text(encoding="utf-8").strip()
            scored.append(
                (
                    best_score + 1,
                    relative,
                    Evidence(
                        kind="kb",
                        source=f"{relative} file",
                        locator=relative,
                        content=whole_file,
                        data={"score": best_score + 1, "recall": "file"},
                    ),
                )
            )
        scored.extend(local_scored)
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:limit]]
