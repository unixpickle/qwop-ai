package main

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"image/png"
	"time"

	"github.com/nfnt/resize"
	"github.com/unixpickle/essentials"
	"github.com/unixpickle/muniverse/chrome"
)

const (
	EnvWaitTimeout    = time.Second * 20
	EnvStepTimeout    = time.Second * 20
	EnvObserveTimeout = time.Second * 20
	EnvResetTimeout   = time.Second * 20
	EnvScoreTimeout   = time.Second * 20
)

// WaitForEnv waits for the environment page to load.
func WaitForEnv(conn *chrome.Conn) (err error) {
	defer essentials.AddCtxTo("WaitForEnv", &err)
	code := `(function() {
        if (window.hasOwnProperty('qwopControl')) {
            return window.qwopControl.wait();
        } else {
            return Promise.reject('game controller is not yet loaded');
        }
    })()`
	for i := 0; i < 20; i++ {
		ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(EnvWaitTimeout))
		defer cancel()
		if err := conn.EvalPromise(ctx, code, nil); err != nil {
			continue
		}
		time.Sleep(time.Second)
	}
	return errors.New("game never started")
}

// StepEnv runs the environment for one timestep.
//
// Returns true if the episode is complete.
func StepEnv(conn *chrome.Conn, action [4]bool) (doneEp bool, err error) {
	defer essentials.AddCtxTo("StepEnv", &err)

	buttonStr := "["
	for i, act := range action[:] {
		if i > 0 {
			buttonStr += ", "
		}
		if act {
			buttonStr += "true"
		} else {
			buttonStr += "false"
		}
	}
	buttonStr += "]"

	code := `(function() {
        window.qwopControl.setButtons(` + buttonStr + `);
        return Promise.resolve(window.qwopControl.step())
    })()`

	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(EnvStepTimeout))
	defer cancel()

	var result bool
	if err := conn.EvalPromise(ctx, code, &result); err != nil {
		return false, err
	}
	return result, nil
}

// ObserveEnv gets an image observation from the
// environment.
//
// The returned array is stored in row-major RGB,
// scaled to [size x size].
func ObserveEnv(conn *chrome.Conn, size int) (data []byte, err error) {
	defer essentials.AddCtxTo("ObserveEnv", &err)

	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(EnvObserveTimeout))
	defer cancel()

	imageData, err := conn.ScreenshotPNG(ctx)
	if err != nil {
		return nil, err
	}
	image, err := png.Decode(bytes.NewReader(imageData))
	if err != nil {
		return nil, err
	}
	resized := resize.Resize(uint(size), uint(size), image, resize.Bilinear)
	res := make([]byte, 0, size*size*3)
	for y := 0; y < size; y++ {
		for x := 0; x < size; x++ {
			r, g, b, _ := resized.At(x, y).RGBA()
			res = append(res, byte(r>>8), byte(g>>8), byte(b>>8))
		}
	}
	return res, nil
}

// ResetEnv resets the environment.
func ResetEnv(conn *chrome.Conn) (err error) {
	defer essentials.AddCtxTo("ResetEnv", &err)
	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(EnvResetTimeout))
	defer cancel()
	code := "Promise.resolve(window.qwopControl.reset())"
	return conn.EvalPromise(ctx, code, nil)
}

// ScoreForEnv gets the current score in the environment.
func ScoreForEnv(conn *chrome.Conn) (score float64, err error) {
	defer essentials.AddCtxTo("ScoreForEnv", &err)
	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(EnvScoreTimeout))
	defer cancel()
	code := "Promise.resolve(window.qwopControl.score())"
	if err := conn.EvalPromise(ctx, code, &score); err != nil {
		return 0, err
	}
	return score, nil
}

// StateForEnv encodes the entire state of an environment
// as a single binary buffer.
func StateForEnv(conn *chrome.Conn, newEpisode bool, imageSize int) ([]byte, error) {
	payload, err := ObserveEnv(conn, imageSize)
	if err != nil {
		return nil, err
	}
	if newEpisode {
		payload = append(payload, 1)
	} else {
		payload = append(payload, 0)
	}
	score, err := ScoreForEnv(conn)
	if err != nil {
		return nil, err
	}
	payload = append(payload, []byte(fmt.Sprintf("%f", score))...)
	return payload, nil
}
