# Primitive positive value check
def has_value(value):
    # check type
	if str == None:
		return False
	if isinstance(value, str):
		return str.strip() != ""
	elif isinstance(value, bool):
		return value
	elif isinstance(value, int) or isinstance(value, float):
		return value != 0
	return True
