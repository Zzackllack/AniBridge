import re
from typing import Optional, Tuple

def parse_absolute_episode(title: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Parses AniWorld titles to extract absolute episode numbers and special indicators.

    Returns:
        A tuple of (episode_number, special_type)
        where episode_number is the integer episode and special_type is something like 'OVA', 'Movie', etc.
    """
    # Check for episode numbers in brackets, e.g., "[Episode 001]", "[Ep 01]"
    # Or just "[001]"
    episode_match = re.search(r'\[(?:Episode\s*|Ep\s*)?(\d+)\]', title, re.IGNORECASE)

    # Special types: [OVA], [Movie], [Special]
    special_match = re.search(r'\[(OVA|Movie|Special|OV|SP)\]', title, re.IGNORECASE)

    episode_number = None
    if episode_match:
        try:
            episode_number = int(episode_match.group(1))
        except ValueError:
            pass

    special_type = special_match.group(1).upper() if special_match else None

    return episode_number, special_type
