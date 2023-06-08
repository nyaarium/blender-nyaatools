from collections import defaultdict
import re


def string_similarity(str1: str, str2: str) -> float:
    if not isinstance(str1, str):
        raise TypeError("str1 must be str type")
    if not isinstance(str2, str):
        raise TypeError("str2 must be str type")

    # Regex removes substr .001, .002, etc. from name
    str1 = re.sub(r"\.\d{3}", "", str1)
    str1 = re.sub(r"_", " ", str1)
    str1 = re.sub(r"\.", " ", str1)
    str2 = re.sub(r"\.\d{3}", "", str2)
    str2 = re.sub(r"_", " ", str2)
    str2 = re.sub(r"\.", " ", str2)

    # , substring_length: Optional[int] = 2, case_sensitive: Optional[bool] = False
    substring_length = 2
    case_sensitive = False

    if not case_sensitive:
        str1 = str1.lower()
        str2 = str2.lower()
    if len(str1) < substring_length or len(str2) < substring_length:
        return 0
    substr_count1 = defaultdict(int)
    for i in range(len(str1) - substring_length + 1):
        substr1 = str1[i:i+substring_length]
        substr_count1[substr1] += 1
    match = 0
    for j in range(len(str2) - substring_length + 1):
        substr2 = str2[j:j+substring_length]
        count = substr_count1[substr2]
        if count > 0:
            substr_count1[substr2] = count - 1
            match += 1
    return (match * 2) / (len(str1) + len(str2) - ((substring_length - 1) * 2))
