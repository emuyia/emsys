# emsys
A bespoke live music companion to MCL built in Pd for RPi.

![alt text](res/emsys.png)

## Features
(Not all implemented)
- Better song mode
  - Send PGM data from custom `mset` file to MD & MnM in Elektron bank syntax (A01, A02, etc.)
- Transport interrupts
  - Queue stop/start transport messages in the last 32nd note of a pattern to resync clock & perform instant pattern swapping. Keeps in time using predictive beat time measurement based on external clock. This allows for more freedom setting mismatching scale lengths.
- Tempo targets
  - Curve to tempos from `mset` data
- Automatic poly mode toggle
  - Toggle MnM poly mode from `mset` data
- Conditional trigs for MnM
- Kaiser inspired generative sequencer modules
- Sampler modules

...

## How to use
A niche hardware set-up is required. Not made for general use.
