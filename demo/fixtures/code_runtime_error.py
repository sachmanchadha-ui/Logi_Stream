def two_sum(nums, target):
    seen = {}
    for i, x in enumerate(nums):
        j = seen[target - x]
        return [j, i]
