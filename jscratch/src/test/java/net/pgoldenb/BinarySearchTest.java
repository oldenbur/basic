package net.pgoldenb;

import com.google.common.collect.Lists;
import org.junit.Test;

import java.util.List;
import java.util.function.Predicate;

import static org.junit.Assert.assertEquals;

public class BinarySearchTest {

    @Test
    public void test1() {
        assertEquals(3, binarySearch(Lists.newArrayList(0, 1, 2, 3, 4, 5, 6, 7, 8, 9), intIsLt(3)));
        assertEquals(0, binarySearch(Lists.newArrayList(0, 1, 2, 3, 4, 5, 6, 7, 8, 9), intIsLt(0)));
        assertEquals(9, binarySearch(Lists.newArrayList(0, 1, 2, 3, 4, 5, 6, 7, 8, 9), intIsLt(9)));

        assertEquals(1, binarySearch(Lists.newArrayList(0, 2, 4, 5), intIsLt(1)));
        assertEquals(3, binarySearch(Lists.newArrayList(0, 2, 4, 7), intIsLt(6)));
    }

    private Predicate<Integer> intIsLt(int target) {
        return  i -> i < target;
    }

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
