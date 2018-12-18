package net.pgoldenb;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import org.junit.Assert;
import org.junit.Test;

import java.util.*;

import static org.junit.Assert.assertEquals;

public class JScratchTest {

    public static final int DIVISOR = 1000000;

    @Test
    public void test1() throws InterruptedException {
        int[] input1 = {1, 2, 3, 4, 5}; assertEquals(2, Arrays.binarySearch(input1, 3));
        int[] input2 = {1, 2, 2, 3, 4, 4, 5}; int i = Arrays.binarySearch(input2, 2);
            Assert.assertTrue(1 <= i); Assert.assertTrue(i <= 2);
        int[] input3 = {1, 2, 4, 5}; assertEquals(-3, Arrays.binarySearch(input3, 3));
        int[] input4 = {1, 2, 3, 4, 5}; assertEquals(-1, Arrays.binarySearch(input4, 0));
        int[] input5 = {1, 2, 3, 4, 5}; assertEquals(-6, Arrays.binarySearch(input5, 7));
//        int[] input6 = {1, 2, 3, 4, 5}; assertEquals(2, Arrays.binarySearch(input6, 3));
    }

}
