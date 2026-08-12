package main

import (
	"fmt"
	"math"
	"testing"
)

type pt struct {
	row  int
	col  int
	dist int
}

func closestXY2D(input [][]string) (int, error) {

	N := len(input)
	queue := []pt{}
	visited := make([][]bool, N)
	for i := 0; i < N; i++ {
		visited[i] = make([]bool, N)
	}
	dirs := [][]int{{-1, 0}, {0, 1}, {1, 0}, {0, -1}}
	result := math.MaxInt

	inGrid := func(r int, c int) bool {
		return r >= 0 && r < N && c >= 0 && c < N
	}

	for r := 0; r < N; r++ {
		for c := 0; c < N; c++ {
			if input[r][c] == "X" {
				visited[r][c] = true
				queue = append(queue, pt{row: r, col: c, dist: 0})
			}
		}
	}

	var cur pt
	for len(queue) > 0 {
		cur, queue = queue[0], queue[1:]
		if input[cur.row][cur.col] == "Y" {
			return cur.dist, nil
		}

		visited[cur.row][cur.col] = true
		for _, dir := range dirs {
			rn := cur.row + dir[0]
			cn := cur.col + dir[1]
			if !inGrid(rn, cn) || visited[rn][cn] {
				continue
			}

			queue = append(queue, pt{row: rn, col: cn, dist: cur.dist + 1})
		}
	}

	return result, fmt.Errorf("No Ys detected")
}

func TestClosestXY2D(t *testing.T) {

	tests := []struct {
		name    string
		input   [][]string
		want    int
		wantErr bool
	}{
		{
			name: "4x4 2-hop",
			input: [][]string{
				{"Y", "O", "O", "O"},
				{"O", "O", "X", "O"},
				{"O", "Y", "O", "O"},
				{"O", "O", "O", "X"},
			},
			want: 2,
		},
		{
			name: "4x4 3-hop",
			input: [][]string{
				{"Y", "O", "O", "O"},
				{"O", "O", "X", "O"},
				{"O", "O", "O", "O"},
				{"Y", "O", "O", "X"},
			},
			want: 3,
		},
		{
			name: "4x4 no Y",
			input: [][]string{
				{"O", "O", "O", "O"},
				{"O", "O", "X", "O"},
				{"O", "O", "O", "O"},
				{"", "O", "O", "X"},
			},
			wantErr: true,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			actual, err := closestXY2D(test.input)
			if test.wantErr {
				if err == nil {
					t.Errorf(`closestXY2D(%s) err == nil, want non-nil`, test.name)
				}
			} else if actual != test.want || err != nil {
				t.Errorf(`closestXY2D(%s) = %d, %v want %d, nil`, test.name, actual, err, test.want)
			}
		})
	}
}
