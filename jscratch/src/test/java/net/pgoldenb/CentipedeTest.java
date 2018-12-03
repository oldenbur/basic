package net.pgoldenb;

import static org.junit.Assert.*;
import org.junit.Test;

import java.util.*;
import java.util.function.Consumer;

public class CentipedeTest {

    static BoardLoc loc(int x, int y) {
        return new BoardLoc(x, y);
    }

    @Test
    public void constructorValid() {
        assertEquals(3, new Centipede(10, 3).length());
    }

    @Test(expected = IllegalArgumentException.class)
    public void constructorInsufficientBoardDim() {
        new Centipede(2, 1);
    }

    @Test(expected = IllegalArgumentException.class)
    public void constructorCentLenTooLarge() {
        new Centipede(10, 6);
    }

    @Test
    public void toStringReturns() {
        Centipede c = new Centipede(7, 3);
        System.out.println(c.toString());
    }

    @Test
    public void boardLocRequiresEquals() {
        Set<BoardLoc> m = new HashSet<>();
        m.add(new BoardLoc(1, 2));
        assertTrue(m.contains(new BoardLoc(1, 2)));
    }

    @Test
    public void moveRight() {
        Creature c = new Creature(Arrays.asList(loc(3, 3), loc(2, 3), loc(1, 3)), 7);
        List<BoardLoc> cm = c.moveTo(loc(4, 3)).segments();
        System.out.println(new Centipede(7, cm).toString());
        assertEquals(3, cm.size());
        assertEquals(loc(4,3), cm.get(0));
        assertEquals(loc(3,3), cm.get(1));
        assertEquals(loc(2,3), cm.get(2));
    }

    @Test
    public void moveDown() {
        Creature c = new Creature(Arrays.asList(loc(3, 3), loc(2, 3), loc(1, 3)), 7);
        List<BoardLoc> cm = c.moveTo(loc(3, 4)).segments();
        System.out.println(new Centipede(7, cm).toString());
        assertEquals(3, cm.size());
        assertEquals(loc(3,4), cm.get(0));
        assertEquals(loc(3,3), cm.get(1));
        assertEquals(loc(2,3), cm.get(2));
    }



}

/**
 * Requirements:
 *   * does board cell contain segment?
 *   * where is the head and tail?
 *   * move: new head segment in unoccupied direction, tail segment disappears and becomes previous second-to-last
 *   * grow: new head segment in unoccupied direction
 */


class BoardLoc {
    int x, y;

    public BoardLoc(int x, int y) {
        this.x = x;
        this.y = y;
    }

    public boolean isAdjacent(BoardLoc otherLoc) {
        int xDelta = Math.abs(x - otherLoc.x);
        int yDelta = Math.abs(y - otherLoc.y);
        return (xDelta == 1 && yDelta == 0) || (xDelta == 0 && yDelta == 1);
    }

    public String toString() {
        return String.format("(%d, %d)", x, y);
    }

    @Override public boolean equals(Object o) {
        return (o != null && o instanceof BoardLoc && ((BoardLoc)o).x == x && ((BoardLoc)o).y == y);
    }

    @Override public int hashCode() {
        int result = 17;
        result = 31 * result + x;
        result = 31 * result + y;
        return result;
    }
}

class Creature {

    private List<BoardLoc> segList;
    private Set<BoardLoc> segSet;
    private int boardDim;

    public Creature(List<BoardLoc> locs, int boardDim) {
        this.segList = new LinkedList<>();
        this.segSet = new HashSet<>(locs.size());
        this.boardDim = boardDim;

        for (BoardLoc loc : locs) {
            validateCreatureSegmentAdjacency(loc);
            validateCreatureSegmentConflict(loc);
            validateCreatureSegmentOnBoard(loc, boardDim);

            segList.add(loc);
            segSet.add(loc);
        }
    }

    private void validateCreatureSegmentOnBoard(BoardLoc loc, int boardDim) {
        if (loc.x < 0 || loc.x >= boardDim || loc.y < 0 || loc.y >= boardDim) {
            throw new IllegalArgumentException(String.format("segment %s not on board of dimension %d", loc, boardDim));
        }
    }

    private void validateCreatureSegmentConflict(BoardLoc loc) {
        if (segSet.contains(loc)) {
            throw new IllegalArgumentException(String.format("initial segment conflict: %s", loc));
        }
    }

    private void validateCreatureSegmentAdjacency(BoardLoc loc) {

        BoardLoc prevLoc = null;
        if (segList.size() > 0) {
            prevLoc = segList.get(segList.size()-1);
        }

        if (prevLoc != null && !loc.isAdjacent(prevLoc)) {
            throw new IllegalArgumentException(
                    String.format("initial location segments not adjacent: %s vs %s", prevLoc, loc)
            );
        }
    }

    public boolean containsLocation(BoardLoc loc) {
        return segSet.contains(loc);
    }

    public int length() {
        return segList.size();
    }

    public List<BoardLoc> segments() {
        return Collections.unmodifiableList(segList);
    }

    public Creature moveTo(BoardLoc loc) {

        BoardLoc head = segList.get(0);
        if (!head.isAdjacent(loc)) {
            throw new IllegalArgumentException(String.format("centipede with head at %s cannot move to %s", head, loc));
        }

        if (loc.x < 0 || loc.y < 0 || loc.x >= boardDim || loc.y >= boardDim) {
            throw new IllegalArgumentException(String.format("centipede cannot move to %s outside of boardDim %d", loc, boardDim));
        }

        List<BoardLoc> newSegs;
        if (segList.size() > 1) {
            newSegs = segList.subList(0, segList.size() - 1);
        } else {
            newSegs = new ArrayList<>();
        }
        newSegs.add(0, loc);

        return new Creature(newSegs, boardDim);
    }
}

class Centipede {

//    enum CentipedeBoardVal { EMPTY, CREATURE }
    private int boardDim;
    private Creature curCreature;

    public Centipede(int boardDim, List<BoardLoc> initCreature) {
        validateBoardDimAndCentLen(boardDim, initCreature.size());

        this.boardDim = boardDim;
        this.curCreature = new Creature(initCreature, boardDim);
    }

    public Centipede(int boardDim, int centLen) {
        this(boardDim, defaultInitCreature(boardDim, centLen));
    }

    private static void validateBoardDimAndCentLen(int boardDim, int centLen) {
        if (boardDim < 3) {
            throw new IllegalArgumentException("boardDim must be greater than 3");
        }
        if (centLen < 1 || centLen > (boardDim / 2)) {
            throw new IllegalArgumentException(String.format("centLen must be 1 <= centLen <= %d", (boardDim / 2)));
        }
    }

    private static List<BoardLoc> defaultInitCreature(int boardDim, int centLen) {

        int ordX = (boardDim/2);
        int ordY = (boardDim/2);

        List<BoardLoc> cLoc = new ArrayList<>(centLen);
        for (int l=0; l < centLen; l++) {
            cLoc.add(new BoardLoc(ordX - l, ordY));
        }

        return cLoc;
    }

    public String toString() {
        StringBuffer b = new StringBuffer();
        b.append("+" + repeat("-", boardDim) + "+\n");
        visitBoardCells(
                boardDim,
                i -> b.append("|"),
                l -> {
                    if (curCreature.containsLocation(l)) {
                        String xStr = String.format("%d", l.x);
                        b.append(xStr.substring(xStr.length()-1));
                    } else {
                        b.append(" ");
                    }
                },
                i -> b.append("|\n")
        );
        b.append("+" + repeat("-", boardDim) + "+\n");

        return b.toString();
    }

    private static void visitBoardCells(
            int boardDim,
            Consumer<Integer> rowBeginConsumer,
            Consumer<BoardLoc> cellConsumer,
            Consumer<Integer> rowEndConsumer
    ) {
        for (int y=0; y < boardDim; y++) {
            rowBeginConsumer.accept(y);
            for (int x=0; x < boardDim; x++) {
                cellConsumer.accept(new BoardLoc(x, y));
            }
            rowEndConsumer.accept(y);
        }
    }

    public int length() {
        return curCreature.length();
    }

    public static String repeat(String s, int n) {
        return new String(new char[n]).replace("\0", s);
    }
}
