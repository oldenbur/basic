package main

import (
	"testing"
	"time"

	"github.com/cihub/seelog"
	"github.com/stretchr/testify/assert"
)

func init() { setupLogging() }

func TestInferTuesday(t *testing.T) {
	defer seelog.Flush()
	s := newRegisterWorker(time.Local)

	testTime := time.Date(2018, 4, 3, 5, 30, 0, 0, time.Local)
	url, err := s.inferReserveUrl(testTime)
	assert.Nil(t, err)
	assert.Equal(t, "https://bouldervalley.consoria.com/2018-04-03/reserve/4578", url)
}