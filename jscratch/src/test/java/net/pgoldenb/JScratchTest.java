package net.pgoldenb;

import org.junit.Test;

import static org.junit.Assert.assertEquals;

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

//        assertEquals(3.0, sublistMedian(new int[]{1, 2, 3, 4, 5}, 0, 5), 0.001);
//        assertEquals(2.5, sublistMedian(new int[]{1, 2, 3, 4}, 0, 4), 0.001);
//        assertEquals(4.0, sublistMedian(new int[]{1, 2, 3, 4, 5, 6, 7, 8}, 1, 6), 0.001);
//        assertEquals(2.5, sublistMedian(new int[]{1, 2, 3, 4, 5, 6, 7, 8}, 0, 4), 0.001);
//        assertEquals(4.5, sublistMedian(new int[]{1, 2, 3, 4, 5, 6, 7, 8}, 2, 6), 0.001);
//        assertEquals(5.5, sublistMedian(new int[]{1, 2, 3, 4, 5, 6, 7, 8}, 2, 8), 0.001);


        int[] nums1 = {1, 3, 5, 7, 9, 11, 13, 15, 17, 19};
        int[] nums2 = {2, 4, 6, 8};
        assertEquals(7.5, findMedianSortedArrays(nums1, nums2), 0.001);
    }

    public double findMedianSortedArrays(int[] nums1, int[] nums2) {

        int div1 = (nums1.length / 2);
        if (nums1.length % 2 == 0) div1 -= 1;
        int div2 = (nums2.length / 2);

        int hopDelta = Math.abs(nums1[div1] - nums2[div2]);

        int hop = 0;
        if (nums1.length <= nums2.length) {
            hop = div1 / 2;

            // TODO: handle smaller going to margins of larger
            if (nums2[div2 - hop] > nums1[nums1.length-1]) {
                // return calcMedian(nums2[div2 - hop])
            }
        } else {
            hop = div2 / 2;
        }

        while (hop > 0) {

            if (nums1[div1] > nums2[div2]) {
                int hopDeltaNew = Math.abs(nums1[div1 - hop] - nums2[div2 + hop]);
                if (hopDeltaNew < hopDelta) {
                    div1 -= hop;
                    div2 += hop;
                }
            } else {
                int hopDeltaNew = Math.abs(nums1[div1 + hop] - nums2[div2 - hop]);
                if (hopDeltaNew < hopDelta) {
                    div1 += hop;
                    div2 -= hop;
                }
            }

            hop /= 2;
        }

        return 0;
    }

    public double sublistMedian(int[] nums, int start, int end) {
        int subLen = end - start;
        int mid = subLen / 2;

        if (subLen % 2 == 1)
            return (double)nums[start + mid];
        else
            return ((double)nums[start + mid-1] + (double)nums[start + mid]) / 2.0;
    }

}
