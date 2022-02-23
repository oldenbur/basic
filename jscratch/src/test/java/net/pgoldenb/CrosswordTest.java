package net.pgoldenb;

import static java.util.stream.Collectors.toList;
import static org.junit.Assert.assertEquals;

import com.google.common.collect.Lists;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;
import org.junit.Test;

public class CrosswordTest {

  /** Hackerrank */
  @Test
  public void crossword() {
        ArrayList<String> board1 =
            Lists.newArrayList(
                "+-++++++++",
                "+-++++++++",
                "+-++++++++",
                "+-----++++",
                "+-+++-++++",
                "+-+++-++++",
                "+++++-++++",
                "++------++",
                "+++++-++++",
                "+++++-++++");
        String words1 = "LONDON;DELHI;ICELAND;ANKARA";
        ArrayList<String> solution1 =
            Lists.newArrayList(
                "+L++++++++",
                "+O++++++++",
                "+N++++++++",
                "+DELHI++++",
                "+O+++C++++",
                "+N+++E++++",
                "+++++L++++",
                "++ANKARA++",
                "+++++N++++",
                "+++++D++++");

        assertEquals(solution1, crosswordPuzzle(board1, words1));

    ArrayList<String> board2 =
        Lists.newArrayList(
            "+-++++++++",
            "+-++++++++",
            "+-------++",
            "+-++++++++",
            "+-++++++++",
            "+------+++",
            "+-+++-++++",
            "+++++-++++",
            "+++++-++++",
            "++++++++++");
    String words2 = "AGRA;NORWAY;ENGLAND;GWALIOR";

    ArrayList<String> solution2 =
        Lists.newArrayList(
            "+E++++++++",
            "+N++++++++",
            "+GWALIOR++",
            "+L++++++++",
            "+A++++++++",
            "+NORWAY+++",
            "+D+++G++++",
            "+++++R++++",
            "+++++A++++",
            "++++++++++");

    assertEquals(solution2, crosswordPuzzle(board2, words2));
  }

  public static List<String> crosswordPuzzle(List<String> crossword, String words) {
    HashSet<String> wordSet = new HashSet<String>(Arrays.asList(words.split(";")));

    Optional<Slot> startCoordOptional = findEmptyCoord(crossword);
    if (!startCoordOptional.isPresent()) {
      return crossword;
    }

    return testRemainingWords(
        crossword,
        wordSet,
        startCoordOptional.get().isHorizontal,
        startCoordOptional.get().startCoord)
        .orElse(crossword);
  }

  static class Coord {

    final int r;
    final int c;

    Coord(int r, int c) {
      this.r = r;
      this.c = c;
    }

    Coord up() {
      return new Coord(r - 1, c);
    }

    Coord left() {
      return new Coord(r, c - 1);
    }

    Coord down() {
      return new Coord(r + 1, c);
    }

    Coord right() {
      return new Coord(r, c + 1);
    }

    boolean isInBounds(List<String> crossword) {
      return (r >= 0 && c >= 0 && r < crossword.size() && c < crossword.get(0).length());
    }

    char charAt(List<String> crossword) {
      if (!isInBounds(crossword)) {
        throw new IllegalStateException(
            String.format(
                "Attempted to get a %s outside of crossword bounds rows = %d cols = %d",
                toString(), crossword.size(), crossword.get(0).length()));
      }
      return crossword.get(r).charAt(c);
    }

    public String toString() {
      return String.format("Coord{r=%d,c=%d}", r, c);
    }
  }

  static class Slot {
    final Coord startCoord;
    final boolean isHorizontal;

    Slot(Coord startCoord, boolean isHorizontal) {
      this.startCoord = startCoord;
      this.isHorizontal = isHorizontal;
    }
  }

  private static Optional<Slot> findEmptyCoord(List<String> crossword) {
    for (int r = 0; r < crossword.size(); r++) {
      for (int c = 0; c < crossword.get(r).length(); c++) {
        Coord coord = new Coord(r, c);
        if (coord.charAt(crossword) == '-') {
          Optional<Coord> startOptional = Optional.empty();
          while (coord.left().isInBounds(crossword) && coord.left().charAt(crossword) != '+') {
            coord = coord.left();
            startOptional = Optional.of(coord);
          }
          if (coord.right().isInBounds(crossword) && coord.right().charAt(crossword) != '+') {
            startOptional = Optional.of(coord);
          }
          if (startOptional.isPresent()) {
            return Optional.of(new Slot(startOptional.get(), true));
          }

          while (coord.up().isInBounds(crossword) && coord.up().charAt(crossword) != '+') {
            coord = coord.up();
            startOptional = Optional.of(coord);
          }
          return Optional.of(new Slot(startOptional.orElse(coord), false));
        }
      }
    }
    return Optional.empty();
  }

  private static Optional<List<String>> testRemainingWords(
      List<String> crossword, Set<String> wordSet, boolean isHorizontal, Coord startCoord) {
    return wordSet.stream()
                  .map(
                      testWord ->
                          testWord(
                              startCoord,
                              testWord,
                              isHorizontal,
                              crossword,
                              wordSet.stream().filter(s -> !s.equals(testWord)).collect(Collectors.toSet())))
                  .filter(Optional::isPresent)
                  .map(Optional::get)
                  .findFirst();
  }

  private static Optional<List<String>> testWord(
      Coord startCoord,
      String curWord,
      boolean isHorizontal,
      List<String> crossword,
      Set<String> wordSet) {

    // Replace the empty slot with the word, if possible
    List<String> newCrossword = crossword.stream().map(String::new).collect(toList());
    Coord letterCoord = startCoord;
    for (int i = 0; i < curWord.length(); i++) {

      // Check to see if we ran out of room to put more letters
      if (!letterCoord.isInBounds(newCrossword) || letterCoord.charAt(newCrossword) == '+') {
        return Optional.empty();
      }

      // Check to see if the letter will work in the slot
      char letter = curWord.charAt(i);
      char existingLetter = letterCoord.charAt(newCrossword);
      if (existingLetter != '-' && existingLetter != letter) {
        return Optional.empty();
      }

      // Update newCrossword with the current letter at letterCoord
      String row = newCrossword.get(letterCoord.r);
      newCrossword.set(
          letterCoord.r,
          letterCoord.c == 0
              ? letter + row.substring(1)
              : letterCoord.c == row.length() - 1
                  ? row.substring(0, row.length() - 1) + letter
                  : row.substring(0, letterCoord.c) + letter + row.substring(letterCoord.c + 1));

      letterCoord = isHorizontal ? letterCoord.right() : letterCoord.down();
    }

    // If there is still room for more letters, the word is too short for the slot
    if (letterCoord.isInBounds(newCrossword) && letterCoord.charAt(newCrossword) != '+') {
      return Optional.empty();
    }

    Optional<Slot> emptyCoordOptional = findEmptyCoord(newCrossword);

    // Success condition
    if (wordSet.isEmpty() && !emptyCoordOptional.isPresent()) {
      return Optional.of(newCrossword);
    }

    return !wordSet.isEmpty() && emptyCoordOptional.isPresent()
        ? testRemainingWords(
        newCrossword,
        wordSet,
        emptyCoordOptional.get().isHorizontal,
        emptyCoordOptional.get().startCoord)
        : Optional.empty();
  }

}
