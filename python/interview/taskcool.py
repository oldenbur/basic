import heapq

def task_cool(tasks: list[str], n: int) -> list[str]:

    task_map: dict[str,int] = {}
    for task in tasks:
        if task not in task_map:
            task_map[task] = 1
        else:
            task_map[task] = task_map[task] + 1
    task_counts = [(count, task) for task, count in task_map.items()]
    heapq.heapify_max(task_counts)

    result = 0
    num_slots = 0
    while len(task_counts) > 0:
        task_max = heapq.heappop_max(task_counts)
        num_slots = task_max[0] * (n-1)
        result += task_max[0] + num_slots
        while num_slots > 0 and len(task_counts) > 0:
            task_sub = heapq.heappop_max(task_counts)
            if task_sub[0] > num_slots:
                task_sub[0] -= num_slots
                heapq.heappush_max(task_sub)
                num_slots = 0
            else:
                num_slots -= task_sub[0]

    result -= int(num_slots/n) if num_slots % n == 0 else int(num_slots/n) + 1
    return result


def main():

    tasks = ["A","A","A","B","B","B"]
    actual1 = task_cool(tasks, 2)
    assert actual1 == 6

    tasks = ["A","A","A","B","B"]
    actual1 = task_cool(tasks, 2)
    assert actual1 == 5

    tasks = ["A","A","A","B","B","C"]
    actual1 = task_cool(tasks, 2)
    assert actual1 == 6

    tasks = ["A","A","A","B","B","C"]
    actual1 = task_cool(tasks, 3)
    assert actual1 == 8

    tasks = ["A","A","A","B","B","C","C"]
    actual1 = task_cool(tasks, 3)
    assert actual1 == 8

    print("SUCCESS")


if __name__ == "__main__":
    main()
