"""短码生成与校验逻辑。"""
import re
import secrets
import string

# 默认短码字符集：大小写字母 + 数字（62 个字符）
ALPHABET = string.ascii_letters + string.digits
DEFAULT_LENGTH = 6

# 自定义短码规则：大小写字母、数字、-、_，长度 4–16
CUSTOM_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{4,16}$")


def generate_code(length: int = DEFAULT_LENGTH) -> str:
    """用密码学安全随机源生成随机短码（默认 6 位 [A-Za-z0-9]）。"""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def is_valid_custom_code(code: str) -> bool:
    """自定义短码是否合法：仅字母/数字/-/_，长度 4–16。"""
    return isinstance(code, str) and CUSTOM_CODE_RE.fullmatch(code) is not None
