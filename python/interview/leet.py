import copy
from builtins import *
from dataclasses import dataclass, field
from bisect import bisect_left
import heapq

INF: int = float('inf')


class ThreeSum:
    def threeSum(self, nums: list[int]) -> list[list[int]]:
        
        nums.sort()
        # l, r = 0, len(nums)-1
        result: set[tuple[int, int, int]] = set()

        i = 0
        while nums[i] <= 0 and i <= len(nums) - 3:

            j, k = i+1, len(nums)-1
            target = abs(nums[i])

            while j < k:
                cur = nums[j] + nums[k]
                if cur == target:
                    result.add((nums[i], nums[j], nums[k]))
                if cur <= target:
                    j += 1
                else:
                    k -= 1                

            i += 1

        return [[n1, n2, n3] for (n1, n2, n3) in result]


    def test_threeSum(self, nums: list[int], expected: set[tuple[int, int, int]]):
        actual = self.threeSum(nums)
        actual_set = set([tuple(l) for l in actual])
        msg = f"threeSum({nums}) = {actual}"
        print(msg)
        assert actual_set == expected, f"Error: {msg}, expected: {expected}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_threeSum([0,0,0], set([(0,0,0)]))
        s.test_threeSum([-1,0,1,2,-1,-4], set([(-1,-1,2), (-1,0,1)]))
        s.test_threeSum([-100,-70,-60,110,120,130,160], set([(-100,-60,160), (-70,-60,130)]))


class RotateImage:
    def rotate(self, matrix: list[list[int]]) -> None:

        def move(r: int, c: int):
            dr = c
            dc = N - r - 1
            matrix[dr][dc] = matrix[r][c]

        N = len(matrix)
        for r in range(int(N/2)):
            for c in range(r, N - r - 1):

                temp = matrix[r][c]
                move(N - c - 1 , r)
                move(N - r - 1, N - c - 1)
                move(c, N - r - 1)
                matrix[c][N - r - 1] = temp


    def test_rotate(self, matrix: list[list[int]], expected: list[list[int]]):
        actual = copy.deepcopy(matrix)
        self.rotate(actual)
        msg = f"rotate({matrix}) = {actual}"
        print(msg)
        assert actual == expected, f"Error: {msg}, expected: {expected}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_rotate([[1, 2, 3], [4, 5, 6], [7, 8, 9]], [[7, 4, 1], [8, 5, 2], [9, 6, 3]])
        s.test_rotate([[1, 2, 3, 4, 5], [6, 7, 8, 9, 10], [11, 12, 13, 14, 15], [16, 17, 18, 19, 20], [21, 22, 23, 24, 25]],
                      [[21, 16, 11, 6, 1], [22, 17, 12, 7, 2], [23, 18, 13, 8, 3], [24, 19, 14, 9, 4], [25, 20, 15, 10, 5]])


class SolveBlockMaze:

    @dataclass(frozen=True, order=True)
    class _Pt:
        r: int
        c: int

    _DIRS = [[-1, 0], [0, 1], [1, 0], [0, -1]]

    def solveBlockMaze(self, maze: list[list[int]]) -> list[_Pt]:
        
        N = len(maze)
        q: list[tuple[int, Solution._Pt]] = [(0, Solution._Pt(0, 0))]
        dist: dict[Solution._Pt, int] = {Solution._Pt(0, 0): 0}
        prev: dict[Solution._Pt, Solution._Pt] = {}

        def _build_path(end: Solution._Pt) -> list[Solution._Pt]:
            result = [end]
            next = prev.get(end, None)
            while next:
                result.append(next)
                next = prev.get(next, None)
            return result

        while q:
            cur = heapq.heappop(q)

            cur_cost, cur_pt = cur
            for dir in Solution._DIRS:
                new_pt = Solution._Pt(cur_pt.r + dir[0], cur_pt.c + dir[1])
                if new_pt.r < 0 or new_pt.r >= N or new_pt.c < 0 or new_pt.c >= N:
                    continue

                orig_dist = dist.get(new_pt, INF)
                new_dist = cur_cost + maze[new_pt.r][new_pt.c]
                if new_dist < orig_dist:

                    dist[new_pt] = new_dist
                    prev[new_pt] = cur_pt
                    heapq.heappush(q, (new_dist, new_pt))

                    if new_pt.r == N-1 and new_pt.c == N-1:
                        return _build_path(new_pt)

        assert False, f"failed to find min path for input maze: {maze}"


    def _test_solveMaze(self, maze: list[list[int]], expected: list[tuple[int, int]]):
        actual = self.solveBlockMaze(maze)
        msg = f"solveMaze({maze}) = {actual}"
        print(msg)
        assert actual == expected, f"Error: {msg}, expected: {expected}"


    @classmethod
    def run_tests(cls):
        s = cls()
        maze1 = [
            [0, 1, 1, 0],
            [0, 1, 1, 1],
            [0, 0, 1, 0],
            [0, 1, 1, 0],
        ]

        s._test_solveMaze(maze1, [
            Solution._Pt(3, 3),
            Solution._Pt(2, 3),
            Solution._Pt(2, 2),
            Solution._Pt(2, 1),
            Solution._Pt(2, 0),
            Solution._Pt(1, 0),
            Solution._Pt(0, 0),
        ])



class RemoveNthFromEnd:
    def removeNthFromEnd(self, head: ListNode | None, n: int) -> ListNode | None:
        cur = head
        len = 0
        for i in range(n+1):
            cur = cur.next
            len += 1
            if not cur and n == len:
                head = head.next
                return head

        trailer = head
        while cur:
            trailer = trailer.next
            cur = cur.next

        if trailer.next:
            trailer.next = trailer.next.next
        
        return head


    def test_removeNth(self, head: str, n: int, expected: str):
        actual = self.removeNthFromEnd(_build_list(head), n)
        actual = _list_str(actual)
        msg = f"swapPairs({head}) = {actual}"
        print(msg)
        assert actual == expected, f"Error: {msg}, expected: {expected}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_removeNth("[1, 2, 3, 4, 5]", 2, "[1, 2, 3, 5]")
        s.test_removeNth("[1, 2, 3, 4, 5]", 1, "[1, 2, 3, 4]")
        s.test_removeNth("[1, 2, 3, 4, 5]", 5, "[2, 3, 4, 5]")
        s.test_removeNth("[1, 2]", 1, "[1]")


# Definition for singly-linked list.
@dataclass
class ListNode[T]:
    val: T
    next: ListNode[T] | None = None


def _build_list(listStr: str) -> ListNode | None:
    """
    "[0,1,2]" -> [0,1,2]
    """
    head: ListNode = None
    cur: ListNode = None
    for item in [int(i.strip()) for i in listStr.removeprefix("[").removesuffix("]").split(",")]:
        if head is None:
            head = ListNode(item)
            cur = head
        else:
            cur.next = ListNode(item)
            cur = cur.next
    return head


def _list_str(head: ListNode | None) -> str:
    """
    [0,1,2] -> "[0,1,2]"
    """
    result = "["
    cur: ListNode = head
    while cur:
        result += str(cur.val) if len(result) == 1 else f", {str(cur.val)}"
        cur = cur.next
    result += "]"
    return result


class SwapListPairs:
    def swapPairs(self, head: ListNode | None) -> ListNode | None:
        if not head:
            return None
        
        cur: ListNode = head
        prev: ListNode = None
        while cur:
            if not cur.next:
                break

            if prev:
                prev.next = cur.next
                cur.next = cur.next.next
                prev.next.next = cur
            else:
                head = cur.next
                cur.next = head.next
                head.next = cur
            prev = cur
            cur = cur.next


        return head

    
    def test_swapPairs(self, head: str, expected: str):
        actual = self.swapPairs(_build_list(head))
        actual = _list_str(actual)
        msg = f"swapPairs({head}) = {actual}"
        print(msg)
        assert actual == expected, f"Error: {msg}, expected: {expected}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_swapPairs("[1, 2, 3, 4]", "[2, 1, 4, 3]")
        s.test_swapPairs("[1, 2, 3, 4, 5]", "[2, 1, 4, 3, 5]")
        s.test_swapPairs("[1]", "[1]")


class DivideIntsBinary:
    def divide(self, dividend: int, divisor: int) -> int:
        
        pow = 1
        pows = [divisor]

        while pows[-1] < dividend:
            pow += 1
            pows.append(pow(divisor, pow))

        # result = 0
        # for i, p in enumerate(len(pows) - 1):
        #     result += 

        return result       


    def testDivideInt(self, dividend: int, divisor: int, expected: int):
        actual = self.divide(dividend, divisor)
        msg = f"divide({dividend}, {divisor}) = {actual}"
        print(msg)
        assert actual == expected, f"Error: {msg}, expected: {expected}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.testDivideInt(11, 3, 3)
        s.testDivideInt(12, 3, 4)
        s.testDivideInt(13, 3, 4)


class MinJump:

    def jump(self, nums: list[int]) -> int:
        
        jumps = 0
        current = 0
        furthest = 0

        for i in range(len(nums) - 1):
            furthest = max(furthest, nums[i] + i)
            if i == current:
                jumps += 1
                current = furthest
        
        return jumps


    def test_minJumps(self, nums: list[int], expected: int) -> int:
        actual = self.jump(nums)
        msg = f"jump({nums}) = {actual}"
        print(msg)
        assert actual == expected, f"Error: {msg}, expected: {expected}"

    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_minJumps([2,3,1,1,4], 2)
        s.test_minJumps([3,4,0,3,0,0,0], 2)
        s.test_minJumps([3,2,1,3,2,1,0], 2)


class CanJump:

    def canJump(self, nums: list[int]) -> bool:
        
        gas = 0
        for i, g in enumerate(nums):
            if g > gas:
                gas = g
            if gas <= 0:
                return i == len(nums) - 1
            
            gas -= 1

        return True


    def canJump_slow(self, nums: list[int]) -> bool:

        def testJumps(idx: int, cache: set[int]) -> bool:

            if idx + nums[idx] >= len(nums) - 1 or idx >= len(nums) - 1:
                return True

            if nums[idx] == 0 or idx in cache:
                return False

            for i in range(1, nums[idx]+1):
                if testJumps(idx + i, cache):
                    return True
                cache.add(idx + i)
        
            return False
        
        return testJumps(0, set())


    def test_canJump(self, nums: list[int], expected: bool):
        actual = self.canJump(nums)
        msg = f"canJump({nums}) = {actual}"
        print(msg)
        assert actual == expected, f"Error: {msg}, expected: {expected}"
        
        
    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_canJump([0], True)
        s.test_canJump([1,2], True)
        s.test_canJump([2,3,1,1,4], True)
        s.test_canJump([3,2,1,0,4], False)


class SpiralOrder:

    type Dir = int

    _RIGHT: Dir = 0
    _DOWN: Dir = 1
    _LEFT: Dir = 2
    _UP: Dir = 3

    _NEXT: dict[Dir, Dir] = {
        _RIGHT: _DOWN,
        _DOWN: _LEFT,
        _LEFT: _UP,
        _UP: _RIGHT,
    }

    _SENTINEL: int = -9999

    def nextrc(self, r: int, c: int, dir: Solution.Dir) -> tuple[int, int]:
        
        if dir == self._RIGHT:
            return (r, c+1)
        elif dir == self._DOWN:
            return (r+1, c)
        elif dir == self._LEFT:
            return (r, c-1)
        elif dir == self._UP:
            return (r-1, c)


    def in_matrix(self, matrix: list[list[int]], r: int, c: int) -> bool:
        return r >= 0 and r < len(matrix) and c >= 0 and c < len(matrix[0])


    def spiralOrder(self, matrix: list[list[int]]) -> list[int]:

        def add_dir(dir: Solution.Dir, r: int, c: int, wip: list[int]):

            if matrix[r][c] == self._SENTINEL:
                return

            while True:
                wip.append(matrix[r][c])
                matrix[r][c] = self._SENTINEL
                rn, cn = self.nextrc(r, c, dir)
                if not self.in_matrix(matrix, rn, cn) or matrix[rn][cn] == self._SENTINEL:
                    break
                r, c = rn, cn

            r, c = self.nextrc(r, c, self._NEXT[dir])
            if self.in_matrix(matrix, r, c):
                add_dir(self._NEXT[dir], r, c, wip)


        if not len(matrix) or not len(matrix[0]):
            return [] 

        wip = []
        add_dir(self._RIGHT, 0, 0, wip)
        return wip


    def test_spiralOrder(self, matrix: list[list[int]], expected: list[int]):
        actual = self.spiralOrder(copy.deepcopy(matrix))
        msg = f"spiralOrder({matrix}) = {actual}"
        print(msg)
        assert actual == expected, f"Error: {msg}, expected: {expected}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_spiralOrder([[1]], [1])
        s.test_spiralOrder([[1,2,3,4],[5,6,7,8],[9,10,11,12]], [1,2,3,4,8,12,11,10,9,5,6,7])


class LetterCombinations:

    _LETTERS: dict[str,list[str]] = {
        "2": ["a", "b", "c"],
        "3": ["d", "e", "f"],
        "4": ["g", "h", "i"],
        "5": ["j", "k", "l"],
        "6": ["m", "n", "o"],
        "7": ["p", "q", "r", "s"],
        "8": ["t", "u", "v"],
        "9": ["w", "x", "y", "z"],        
    }

    def letterCombinations(self, digits: str) -> list[str]:
        
        def add_letters(digits: str, wip: list[str]) -> list[str]:
            if len(digits) < 1:
                return wip
            
            new_wip = []
            if len(wip) > 0:
                for wips in wip:
                    for l in self._LETTERS[digits[0]]:
                        new_wip.append(wips + l)
            else:
                new_wip = self._LETTERS[digits[0]]

            return add_letters(digits[1:], new_wip)            

        return add_letters(digits, [])


    def test_letterCombinations(self, digits: str, expected: list[str]):
        actual = self.letterCombinations(digits)
        msg = f"letterCombinations({digits}) = {actual}"
        print(msg)
        assert actual == expected, f"Error: {msg}, expected: {expected}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_letterCombinations("23", ["ad","ae","af","bd","be","bf","cd","ce","cf"])
        s.test_letterCombinations("678", [])


# Definition for a Node.
@dataclass
class Node[T]:
    val: T
    neighbors: list[Node] = field(default_factory=list)


class CloneGraph:
    def cloneGraph(self, node: Node) -> Node:
        if node is None:
            return None

        return self.build_graph(self.build_adj(node))


    def build_adj(self, node: Node) -> list[list[int]]:
        queue = [node]
        nodes: dict[int, list[int]] = {}

        while queue:
            cur = queue.pop(0)
            if cur.val not in nodes:
                nodes[cur.val] = [neigh.val for neigh in cur.neighbors]
                for neigh in cur.neighbors: queue.append(neigh)

        return [neigh for _, neigh in sorted(nodes.items())]


    def build_graph(self, adj: list[list[int]]) -> Node:
        nodes = {i: Node(val=i+1) for i in range(len(adj))}
        for i, adjl in enumerate(adj):
            nodes[i].neighbors = [nodes[j-1] for j in adjl]
        return nodes[0]


    def test_cloneGraph(self, input: list[list[int]]):
        actual = self.build_adj(self.cloneGraph(self.build_graph(input)))
        msg = f"cloneGraph({input}) = {actual}"
        print(msg)
        assert actual == input, f"Error {msg}, expected {input}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_cloneGraph([[2,4], [1,3], [2,4], [1,3]])
        s.test_cloneGraph([[]])


@dataclass
class TreeNode[T]:
    val: T = 0
    left: TreeNode | None = None
    right: TreeNode | None = None


class TreeLinkedList:
    def flatten(self, root: TreeNode | None) -> None:
        
        def flatten_branches(node: TreeNode | None) -> TreeNode | None:

            if node is None:
                return None

            end_left = flatten_branches(node.left) if node.left is not None else None
            end_right = flatten_branches(node.right) if node.right is not None else None
            
            if end_left is not None:
                node_tmp = node.right
                node.right = node.left
                node.left = None
                end_left.right = node_tmp
                return end_right if end_right is not None else end_left
            
            elif end_right is not None:
                return end_right

            return node
        
        flatten_branches(root)


    def test_treeFlatten(self, root: TreeNode | None, expected: TreeNode | None):
        actual = copy.deepcopy(root)
        self.flatten(actual)
        msg = f"flatten({root}) = {actual}"
        print(msg)
        assert actual == expected, f"Error in {msg}, expected: {expected}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_treeFlatten(
            TreeNode(val=1, 
                     left=TreeNode(
                         val=2,
                         left=TreeNode(val=3),
                         right=TreeNode(val=4)
                     ),
                     right=TreeNode(
                         val=5,
                         right=TreeNode(val=6)
                     )),
            TreeNode(val=1, 
                     right=TreeNode(val=2, 
                        right=TreeNode(val=3, 
                            right=TreeNode(val=4,
                                right=TreeNode(val=5,
                                    right=TreeNode(val=6)))))))
        s.test_treeFlatten(
            TreeNode(val=1,
                left=TreeNode(val=2,
                    left=TreeNode(val=3))),
            TreeNode(val=1,
                right=TreeNode(val=2,
                    right=TreeNode(val=3)))
        )


class WordExists:
    def exist(self, board: list[list[str]], word: str) -> bool:
        
        def find_word(row: int, col: int, remaining: str, used: set[tuple[int,int]]) -> bool:    

            if (row, col) in used:
                return False
            used.add((row, col))
            
            if len(remaining) == 0:
                return True

            letter = remaining[0]
            if row > 0 and board[row-1][col] == letter and find_word(row-1, col, remaining[1:], used.copy()):
                return True
            if col > 0 and board[row][col-1] == letter and find_word(row, col-1, remaining[1:], used.copy()):
                return True
            if row < len(board) - 1 and board[row+1][col] == letter and find_word(row+1, col, remaining[1:], used.copy()):
                return True
            if col < len(board[0]) - 1 and board[row][col+1] == letter and find_word(row, col+1, remaining[1:], used.copy()):
                return True
        
            return False

        for r, _ in enumerate(board):
            for c, _ in enumerate(board[r]):
                if board[r][c] == word[0]:
                    if find_word(r, c, word[1:], set()):
                        return True

        return False



    def test_wordExist(self, board: list[list[str]], word: str, expected: bool):
        actual = self.exist(board, word)
        msg = f"wordExist({board}, {word}) = {actual}"
        print(msg)
        assert actual == expected, f"Error for {msg}, expected {expected}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_wordExist([["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]], "ABCCED", True)
        s.test_wordExist([["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]], "ASFBA", True)
        s.test_wordExist([["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]], "SCFBC", True)
        s.test_wordExist([["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]], "ABCCEC", False)
        s.test_wordExist([["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]], "ABCCXE", False)
        s.test_wordExist([["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]], "SCFBS", False)
        s.test_wordExist([["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]], "SCFBCC", False)
        s.test_wordExist([["A","B","C","E"],["S","F","E","S"],["A","D","E","E"]], "ABCESEEEFS", True)


def binary_search[T](input: list[T], target: T) -> int:

    low = 0
    high = len(input) - 1

    while low <= high:

        mid = low + (high - low) // 2
        if input[mid] == target:
            return mid
        elif target < input[mid]:
            high = mid - 1
        else:
            low = mid + 1
        
    return low


class SearchMatrix:
    def searchMatrix(self, matrix: list[list[int]], target: int) -> bool:
        row_headers = [r[0] for r in matrix]

        row = binary_search(row_headers, target)
        if row < len(matrix) and matrix[row][0] == target:
            return True
        
        row -= 0 if row == 0 else 1        
        col = binary_search(matrix[row][:], target)
        if col >= len(matrix[0]):
            return False
        return matrix[row][col] == target


    def test_searchMatrix[T](self, input: list[list[int]], target: int, expected: bool):
        actual = self.searchMatrix(input, target)
        print(f"searchMatrix({input}, {target}) = {actual}")
        assert actual == expected, f"Expected searchMatrix({input}, {target}) to equal {expected}, got {actual}"


    @staticmethod
    def test_binarySearch[T](input: list[T], target: T, expected: T):
        actual = binary_search(input, target)
        print(f"binary_search({input}, {target}) = {actual}")
        assert actual == expected, f"Expected binary_search({input}, {target}) to equal {expected}, got {actual}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 1, True)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 5, True)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 7, True)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 10, True)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 16, True)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 20, True)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 23, True)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 30, True)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 60, True)

        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 0, False)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 4, False)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 9, False)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 17, False)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 21, False)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 50, False)
        s.test_searchMatrix([[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 1776, False)

        # Solution.test_binarySearch([1, 3, 5, 7, 9, 11], 10, 5)
        # Solution.test_binarySearch([1, 3, 5, 7, 9, 11], 0, 0)
        # Solution.test_binarySearch([1, 3, 5, 7, 9, 11], 12, 6)
        # Solution.test_binarySearch([1, 3, 5, 7, 9, 11], 3, 1)
        # Solution.test_binarySearch([1, 3, 5, 7, 9, 11], 4, 2)
        # Solution.test_binarySearch([1, 3, 5, 7, 9, 11], 9, 4)
        # Solution.test_binarySearch([1, 3, 5, 7, 9, 11], 8, 4)


class MergeSpans:
    def merge(self, intervals: list[list[int]]) -> list[list[int]]:

        if len(intervals) <= 1:
            return intervals

        intervals.sort(key=lambda interval: interval[0])
        result = [intervals.pop(0)]
        while intervals:
            next = intervals.pop(0)
            if next[0] > result[-1][1]:
                result.append(next)
            else:
                result[-1][1] = max(result[-1][1],next[1])

        return result
        

    def test_merge[T](self, input: list[list[int]], expected: list[list[int]]):
        actual = self.merge(input.copy())
        print(f"merge({input}) = {actual}")
        assert actual == expected, f"Expected merge({input}) to equal {expected}, got {actual}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_merge([[8,10],[2,6],[1,3],[15,18],[10,11]], [[1,6],[8,11],[15,18]])
        s.test_merge([[1,3],[2,7],[8,9],[4,11],[15,18]], [[1,11],[15,18]])


def reverse[T](input: list[T], i: int = None, j: int = None):
    """
    Reverse the elements of the input list in place from index i to index j inclusive.
    """
    i = 0 if i is None else i
    j = len(input) - 1 if j is None else j
    while i < j:
        swap(input, i, j)
        i += 1
        j -= 1


def swap[T](input: list[T], i: int, j: int):
        """
        Swap the items at index i and j in the input list in place. 
        """
        if i < 0 or i >= len(input) or j < 0 or j >= len(input):
            raise ValueError(f"Invalid swap parameters - i: {i}  j: {j}  len(input): {len(input)}")
        if i == j:
            return
        
        tmp = input[j]
        input[j] = input[i]
        input[i] = tmp


def permutations[T](input: list[T]) -> set[tuple[T]]:
    """
    Returns a list of all ordering permutations of the items in the input list.
    """

    def permutations_heap(k: int, input: list[T]):
        if k == 1:
            result.add(tuple(input.copy()))
            return
        
        permutations_heap(k-1, input)
        for i in range(k-1):
            if k % 2 == 0:
                swap(input, i, k-1)
            else:
                swap(input, 0, k-1)
            permutations_heap(k-1, input)

    result = set()
    permutations_heap(len(input), input)
    return result


class Permutations:

    def test_permuations[T](self, input: list[T], expected: set[list[T]]):
        actual = permutations(input)
        print(f"permutations({input}) = {actual}")
        assert actual == expected, f"Expected intPermuations({input}) to equal {expected}, got {actual}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_permuations([1, 2, 3], {(1, 2, 3), (1, 3, 2), (2, 1, 3), (2, 3, 1), (3, 1, 2), (3, 2, 1)})   
        s.test_permuations([1, 1, 2], {(1, 1, 2), (1, 2, 1), (2, 1, 1)})   


class NextPermutation:
    def nextPermutation(self, nums: list[int]) -> None:
        """
        Do not return anything, modify nums in-place instead.
        """
 
        i = len(nums) - 1
        while i > 0 and nums[i-1] >= nums[i]: i -= 1
        if i == 0:
            reverse(nums)
            return

        l = len(nums) - 1
        while l > 0 and nums[i-1] >= nums[l]: l -= 1
        swap(nums, i-1, l)
        reverse(nums, i)


    def test_nextPermutation(self, input: list[int], expected: list[int]):
        actual = input.copy()
        self.nextPermutation(actual)
        print(f"nextPermutation({input}) = {actual}")
        assert actual == expected, f"Expected nextPermutation({input}) to equal {expected}, got {actual}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_nextPermutation([2, 1, 5, 4], [2, 4, 1, 5])
        s.test_nextPermutation([1, 1, 5, 1], [1, 5, 1, 1])
        s.test_nextPermutation([5, 4, 3, 2], [2, 3, 4, 5])
        s.test_nextPermutation([1, 4, 3, 2], [2, 1, 3, 4])
        s.test_nextPermutation([1, 1], [1, 1])
        s.test_nextPermutation([5, 1, 1], [1, 1, 5])


class GenerateParenthesis:
    def generateParenthesis(self, n: int) -> list[str]:

        def add_parens(left: int, right: int, prefix: str):
            if len(prefix) == 2*n:
                res.append(prefix)
                return

            if left < n:
                add_parens(left+1, right, prefix + '(')

            if right < left:
                add_parens(left, right+1, prefix + ')')

        res = []
        add_parens(0, 0, "")
        return res


    def test_parens(self, input: int, expected: list[str]):
        actual = self.generateParenthesis(input)
        print(f"generateParenthesis({input}) = {actual}")
        assert actual == expected, f"Expected generateParenthesis({input}) to equal {expected}, got {actual}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_parens(2, ["(())", "()()"])
        s.test_parens(3, ["((()))", "(()())", "(())()", "()(())", "()()()"])
    

class RomanNumerals:
    def intToRoman(self, num: int) -> str:
        denoms = {
            1000: "M",
            900: "CM",
            500: "D",
            400: "CD",
            100: "C",
            90: "XC",
            50: "L",
            40: "XL",
            10: "X",
            9: "IX",
            5: "V",
            4: "IV",
            1: "I"
        }

        result = ""
        for denom in sorted([k for k in denoms], reverse=True):
            while (num >= denom):
                result += denoms[denom]
                num -= denom
        return result

    
    def test_intToRoman(self, input: int, expected: str):
        actual = self.intToRoman(input)
        print(f"intToRoman({input}) = {actual}")
        assert actual == expected, f"Expected intToRoman({input}) to equal {expected}, got {actual}"


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_intToRoman(635, "DCXXXV")
        s.test_intToRoman(439, "CDXXXIX")
        s.test_intToRoman(1994, "MCMXCIV")
        s.test_intToRoman(3749, "MMMDCCXLIX")
        

class MaxWater:
    """
    https://leetcode.com/problems/container-with-most-water/submissions/2046249417/?submissionId=2046210429
    """
    def maxArea(self, height: list[int]) -> int:

        if len(height) < 2:
            raise ValueError(f"unexpected input length: {len(height)}")
     
        lptr, rptr, max_water = 0, len(height) - 1, 0
        max_pos = None

        while lptr < rptr:
            cur = min(height[lptr], height[rptr]) * (rptr - lptr)
            if cur > max_water:
                max_water = cur
                max_pos = (lptr, rptr)
            if height[lptr] <= height[rptr]:
                lptr += 1
            else:
                rptr -= 1

        print(f"maxArea - max_water: {max_water}  max_pos: {max_pos}")
        return max_water



    def test_maxArea(self, input: list[int], expected: int):
        actual = self.maxArea(input)
        print(f"maxArea({input}) = {actual}")
        assert actual == expected


    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_maxArea([1,2,1], 2)
        s.test_maxArea([1,2,1,3,2], 6)
        s.test_maxArea([1,3,1,2,2], 6)
        s.test_maxArea([3,3,1,1,1,1], 5)
        s.test_maxArea([1,8,6,2,5,4,8,3,7], 49)


class LongestSubstring:
    """
    https://leetcode.com/problems/longest-substring-without-repeating-characters/description/?submissionId=2046210429
    """
    def lengthOfLongestSubstring(self, s: str) -> int:
        sub_chars: dict[str, int] = {}

        longest = 0
        i_start = 0
        for i, c in enumerate(s):
            if not c in sub_chars:
                sub_chars[c] = i
                longest = max(longest, len(sub_chars))
                continue

            # 1. compute the current string length and update longest
            i_last = sub_chars[c]
            longest = max(longest, i - i_last)
            # 2. remove letters from sub_chars starting at the last occurrence back to i_start
            for r in s[i_start:i_last]:
                del sub_chars[r]
            sub_chars[c] = i
            # 3. update i_start to last_occ+1
            i_start = i_last+1

        return max(longest, len(sub_chars))
    
    def test_longestSubstring(self, input: str, expected: int):
        actual = self.lengthOfLongestSubstring(input)
        print(f"longestSubstring({input}) = {actual}")
        assert actual == expected

    @classmethod
    def run_tests(cls):
        s = cls()
        s.test_longestSubstring("abcabcbb", 3)
        s.test_longestSubstring("abcdabcbb", 4)
        s.test_longestSubstring("abcabcdbb", 4)
        s.test_longestSubstring("bbbbb", 1)
        s.test_longestSubstring("pwwkew", 3)
        s.test_longestSubstring("pwwke", 3)
        s.test_longestSubstring("dvdf", 3)


def main():
    Solution.run_tests()

if __name__ == "__main__":
    main()