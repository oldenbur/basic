import pytest
import heapq
from typing import TypeAlias

Coord: TypeAlias = tuple[int, int]

_DIRECTIONS: list[tuple[int, int]] = [[-1, 0], [0, -1], [1, 0], [0, 1]]


def reconstruct_path(came_from: map(Coord, Coord), current: Coord) -> list[Coord]:
    route = [current]
    current = came_from[current]

    while current is not None:
        route.insert(0, current)
        current = came_from.get(current)
    return route


def h(n: int, coord: Coord) -> float:
    nf = float(n)
    return ((nf - float(coord[0]) - 1.) + (nf - float(coord[1]) - 1.)) / (2. * nf)
    # return 0.


def demo_robot_astar(n: int, grid: list[list[int]]) -> list[Coord]:

    queue = [(h(n, (0, 0)), (0, 0))]
    came_from: dict(Coord, Coord) = {}
    g_scores: dict(Coord, int) = {(0, 0): 0}  # cost to Coord
    f_scores: dict(Coord, float) = {(0, 0): 2*(n-1)}  # Coord optimality

    while queue:
        (g, current) = heapq.heappop(queue)
        if current[0] == n-1 and current[1] == n-1:
            return reconstruct_path(came_from, current)

        for direction in _DIRECTIONS:
            next = (current[0] + direction[0], current[1] + direction[1])
            if next[0] < 0 or next[0] >= n or next[1] < 0 or next[1] >= n:
                continue

            tentative_g = g_scores[current] + grid[next[0]][next[1]]
            if next not in g_scores or tentative_g < g_scores[next]:
                came_from[next] = current
                g_scores[next] = tentative_g
                f_scores[next] = tentative_g + h(n, next)
                heapq.heappush(queue, (f_scores[next], next))

    raise ValueError(f"processing failure")


def main():

    # input1 = [
    #     [0, 1, 0, 0],
    #     [0, 1, 1, 1],
    #     [0, 0, 1, 0],
    #     [1, 1, 1, 0]
    # ]
    # actual1 = demo_robot(4, input1)
    # assert actual1 == [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (2, 3), (3, 3)]

    input2 = [
        [0, 1, 1, 0, 0, 0],
        [0, 1, 0, 0, 1, 0],
        [0, 1, 0, 1, 1, 0],
        [0, 1, 0, 0, 1, 0],
        [0, 1, 1, 0, 1, 0],
        [0, 0, 0, 0, 1, 0]
    ]
    actual2 = demo_robot_astar(6, input2)
    assert actual2 == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (5, 1), (5, 2), (5, 3),
    (4, 3), (3, 3), (3, 2), (2, 2), (1, 2), (1, 3), (0, 3), (0, 4), (0, 5), (1, 5), (2, 5), (3, 5),
    (4, 5), (5, 5)]

    print("SUCCESS")

if __name__ == "__main__":
    main()
