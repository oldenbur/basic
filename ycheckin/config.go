package main

import "time"

const (
	scheduleAheadDurationDefault = 48 * time.Hour
	registerRetryWaitDefault     = time.Second
	registerRetryMaxDefault      = 3600
	registerRetryLogIntvlDefault = 100
)

func NewConfigBuilder() *configBuilder {
	return &configBuilder{&ycheckinConfig{
		time.Local,
		scheduleAheadDurationDefault,
		registerRetryWaitDefault,
		registerRetryMaxDefault,
		registerRetryLogIntvlDefault,
	}}
}

type configBuilder struct {
	config *ycheckinConfig
}

func (c *configBuilder) WithLocation(loc *time.Location) *configBuilder {
	c.config.loc = loc
	return c
}

func (c *configBuilder) WithScheduleAheadDuration(d time.Duration) *configBuilder {
	c.config.scheduleAheadDuration = d
	return c
}

func (c *configBuilder) WithRegisterRetryWait(d time.Duration) *configBuilder {
	c.config.registerRetryWait = d
	return c
}

func (c *configBuilder) WithRegisterRetryMax(i int) *configBuilder {
	c.config.registerRetryMax = i
	return c
}

func (c *configBuilder) WithRegisterRetryLogIntvl(i int) *configBuilder {
	c.config.registerRetryLogIntvl = i
	return c
}

func (c *configBuilder) Build() *ycheckinConfig {
	return c.config
}

type ycheckinConfig struct {
	loc                   *time.Location
	scheduleAheadDuration time.Duration
	registerRetryWait     time.Duration
	registerRetryMax      int
	registerRetryLogIntvl int
}

func (c *ycheckinConfig) RegisterLocation() *time.Location     { return c.loc }
func (c *ycheckinConfig) ScheduleAheadDuration() time.Duration { return c.scheduleAheadDuration }
func (c *ycheckinConfig) RegisterRetryWait() time.Duration     { return c.registerRetryWait }
func (c *ycheckinConfig) RegisterRetryMax() int                { return c.registerRetryMax }
func (c *ycheckinConfig) RegisterRetryLogIntvl() int           { return c.registerRetryLogIntvl }
