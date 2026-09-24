import re

with open("tests/test_converters_and_resilience.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace imports
content = content.replace("from ai.common import safe_int, safe_list, safe_dict, safe_str", "from ai.common.schemas import clean_int_value as safe_int, clean_list_value as safe_list, clean_dict_value as safe_dict, clean_str_value as safe_str")

# Also rename the test class just to be more descriptive
content = content.replace("TestSafeConverters", "TestCleanConverters")

with open("tests/test_converters_and_resilience.py", "w", encoding="utf-8") as f:
    f.write(content)
