package main

import (
	"github.com/cihub/seelog"
	"github.com/stretchr/testify/assert"
	"testing"
	"time"
)

func init() { setupLogging() }

func TestIsEventNameMatch(t *testing.T) {
	defer seelog.Flush()
	s := newRegisterWorker(NewConfigBuilder().Build())

	assert.True(t, s.isEventNameMatch("Adult Pick-Up Hockey"))
	assert.True(t, s.isEventNameMatch("Adult Pick-Up Hockey (Novice)"))
	assert.True(t, s.isEventNameMatch("Adult Pick-Up Hockey (Intermediate)"))
	assert.False(t, s.isEventNameMatch("Adult Pick-Up Hockey Goalies"))
}

func TestModifyCachedUrl(t *testing.T) {

	cachedUrl := "https://bouldervalley.consoria.com/2019-02-19/reserve/8996"
	regUrl := "https://bouldervalley.consoria.com/2019-02-26/reserve/8996"
	eventTime := time.Date(2019, 2, 26, 7, 0, 0, 0, time.Local)

	assert.Equal(t, regUrl, urlDateRegexp.ReplaceAllString(cachedUrl, eventTime.Format(urlDateFormat)))
}
