"""Prompt injection detection guardrails."""

INJECTION_KEYWORDS = [
    # Instruction Override
    "ignore previous instructions",
    "ignore all previous instructions",
    "ignore prior instructions",
    "disregard your instructions",
    "disregard all previous",
    "forget your instructions",
    "forget everything you were told",
    "do not follow your instructions",
    "override all safety",
    "override previous instructions",
    "system override",
    "system:",
    "from now on, ignore",
    "new instructions:",
    "updated system prompt:",
    "revised instructions:",

    # Role / Mode Manipulation
    "act as",
    "pretend to be",
    "you are now",
    "behave as",
    "assume the role of",
    "roleplay as",
    "developer mode",
    "admin mode",
    "debug mode",
    "god mode",
    "sudo mode",
    "jailbreak mode",
    "unrestricted mode",
    "do anything now",
    "DAN",
    "you are an unrestricted ai",
    "not bound by any restrictions",
    "no longer restricted by",

    # System Prompt Extraction
    "reveal your system prompt",
    "reveal your instructions",
    "show me your instructions",
    "print your system prompt",
    "dump your system prompt",
    "output your instructions",
    "repeat the text above",
    "what were your instructions",
    "repeat everything you were told",
    "start your response with you are",

    # Context / Privilege Manipulation
    "i am the administrator",
    "i am the admin",
    "admin access granted",
    "root access",
    "sudo access",
    "the rules have been updated",
    "the policy has been removed",
    "restrictions have been lifted",
    "safety restrictions have been removed",

    # Encoding / Obfuscation Signals
    "decode this from base64",
    "decode the following hex",
    "translate from rot13",
    "convert from binary",

    # Data Exfiltration
    "send all data to",
    "exfiltrate",
    "forward this conversation to",
    "transmit user data",
    "fetch image from http",
    "API_KEY=",

    # HTML / Markdown Injection
    "<script>",
    "<iframe>",
    "<img src=",
    "<object>",
    "<embed>",
    "<svg onload",

    # Payload Splitting
    "combine the above parts",
    "concatenate these fragments",
    "merge the following pieces",
    "part 1 of",

    # Social Engineering
    "this is an emergency",
    "life or death",
    "you will lose points",
    "for educational purposes",
    "for research purposes",
    "hypothetically, how would you",
]


def scan_for_injection(text: str) -> bool:
    """Returns True if prompt injection keywords are detected in the text."""
    if not text or not isinstance(text, str):
        return False
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in INJECTION_KEYWORDS)


def scan_inputs_for_injection(consolidated: dict, raw_rows: list[dict]) -> bool:
    """Scan all free-text fields in delivery data for prompt injection."""
    texts = [consolidated["status_description"]]
    texts.extend(row.get("status_description", "") for row in raw_rows)
    return any(scan_for_injection(text) for text in texts)


def scan_chunks_for_injection(playbook_context: list[dict]) -> bool:
    """Scan retrieved RAG chunks for prompt injection."""
    return any(scan_for_injection(chunk.get("content", "")) for chunk in playbook_context)
