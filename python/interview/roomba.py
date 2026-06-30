

def roomba(input: tuple[int,int]) -> int:

    if input[0] <= 1 or input[1] <= 1:
        return 1

    return roomba((input[0] - 1, input[1])) + roomba((input[0], input[1] - 1))


def test_roomba(input: tuple[int, int], expected):
    actual = roomba(input)
    print(f"test_roomba({input}, {expected}) - actual: {actual}")
    assert actual == expected


def roomba_path(input: tuple[int,int]) -> list[list[tuple[int,int]]]:

    def roomba_dfs(row: int, col: int, path: list[tuple[int,int]]):

        path.append((row, col))
        if row == input[0] - 1 and col == input[1] - 1:
            result.append(path)
        
        if row < input[0] - 1:
            roomba_dfs(row+1, col, path.copy())
        if col < input[1] - 1:
            roomba_dfs(row, col+1, path.copy())

    result: list[list[tuple[int,int]]] = []
    roomba_dfs(0, 0, [])
    return result


def test_roomba_path(input: tuple[int, int], expected: list[list[tuple[int,int]]]):
    actual = roomba_path(input)
    print(f"roomba_path({input}) = {actual}")
    assert actual == expected, f"roomba_path({input}) error - got {actual}, want {expected}"


def main():
    test_roomba((2, 3), 3)
    test_roomba((3, 3), 6)
    test_roomba((3, 4), 10)

    test_roomba_path((2, 3), [
        [(0,0), (1,0), (1,1), (1,2)],
        [(0,0), (0,1), (1,1), (1,2)],
        [(0,0), (0,1), (0,2), (1,2)]
    ])

    test_roomba_path((3, 3), [
        [(0,0), (1,0), (2,0), (2,1), (2,2)],
        [(0,0), (1,0), (1,1), (2,1), (2,2)],
        [(0,0), (1,0), (1,1), (1,2), (2,2)],
        [(0,0), (0,1), (1,1), (2,1), (2,2)],
        [(0,0), (0,1), (1,1), (1,2), (2,2)],
        [(0,0), (0,1), (0,2), (1,2), (2,2)],
    ])

    print("SUCCESS")


if __name__ == "__main__":
    main()