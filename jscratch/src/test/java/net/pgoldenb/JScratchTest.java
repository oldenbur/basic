package net.pgoldenb;

import com.google.common.collect.Lists;
import org.junit.Test;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.function.Predicate;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

/*
 *  * Design Patterns
 *  * Adjacency Matrix graphs
 *
 *  * Dijkstras Algo
 *  * A-star Algo
 *  * Travelling Salesman
 *  * Knapsack problem
 *  * n-choose
 */

public class JScratchTest {

    @Test
    public void test1() {
        assertEquals(3, binarySearch(Lists.newArrayList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10), intIsLt));
    }

    private static final int INT_TARGET = 4;

    private Predicate<Integer> intIsLt = i -> i < INT_TARGET;

    private <T> int binarySearch(List<T> data, Predicate<T> isLt) {

        int winMin = 0, winMax = data.size() - 1;
        int guess = (winMax + winMin) / 2;

        while (winMax - winMin > 1) {
            if (isLt.test(data.get(guess))) {
                winMin = guess;
            } else {
                winMax = guess;
            }
            guess = (winMax + winMin) / 2;
        }

        T val = data.get(guess);
        if (isLt.test(val))
            guess += 1;

        return guess;
    }
}
