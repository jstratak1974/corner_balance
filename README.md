# Corner Balance Lab

A touch-friendly Python/Kivy application for Android and desktop that turns four scale readings into a practical static corner-balance report. It also estimates vertical centre-of-gravity height from a rear-axle lift test.

The app is an independent implementation based on the concepts and workshop procedure in Rob Robinette's corner-weight and CG-height resources:

- [Corner Balance Calculator](https://robrobinette.com/corner_weight_calc.htm)
- [How to Corner Balance Your Car](https://robrobinette.com/corner_weight.htm)
- [CG Height Calculator](https://robrobinette.com/cg_height_calc.htm)

It is not affiliated with or endorsed by the reference-site author.

## Features

- Four-corner input for left-front (LF), right-front (RF), left-rear (LR), and right-rear (RR) loads
- Pounds or kilograms—the calculations work with either when all readings use the same unit
- Total, front/rear, and left/right weights and percentages
- Cross weight using the RF + LR diagonal
- Bite and wedge-delta calculations
- Adjustable target cross percentage, with 50% as the default neutral starting point
- Target load and required load change for every wheel
- Rear-lift CG-height estimator with measurement-sensitivity feedback
- Built-in setup guide and safety reminders
- One-tap copy for calculation reports
- Local JSON session save/load in the app's private storage
- No network access and no Android permissions required at runtime
- Pure-Python self-test mode that does not require Kivy

## App layout

The four readings must match the car's physical orientation:

| | Left | Right |
|---|---:|---:|
| **Front** | LF | RF |
| **Rear** | LR | RR |

The Android interface contains four tabs:

1. **Balance** — measurements, current balance, and target corner loads.
2. **CG Height** — level and rear-raised measurements for a CG-height estimate.
3. **Setup Guide** — a condensed, in-app workshop checklist.
4. **About** — references, data handling, and limitations.

## Corner-balance calculations

Let the four scale readings be \(W_{LF}\), \(W_{RF}\), \(W_{LR}\), and \(W_{RR}\).

### Totals and distributions

\[
W_T = W_{LF} + W_{RF} + W_{LR} + W_{RR}
\]

\[
W_F = W_{LF} + W_{RF}, \qquad W_R = W_{LR} + W_{RR}
\]

\[
W_L = W_{LF} + W_{LR}, \qquad W_{Right} = W_{RF} + W_{RR}
\]

Each percentage is its subtotal divided by \(W_T\), multiplied by 100.

### Cross weight, bite, and wedge delta

This project follows the reference calculator's RF + LR definition of cross weight:

\[
W_X = W_{RF} + W_{LR}
\]

\[
Cross\% = 100\frac{W_X}{W_T}
\]

Rear bite is:

\[
Bite = W_{LR} - W_{RR}
\]

Wedge delta is the difference between diagonal totals:

\[
Wedge\ Delta = (W_{RF}+W_{LR})-(W_{LF}+W_{RR})
\]

A positive value means the RF + LR diagonal carries more static load than the LF + RR diagonal.

### Target corner loads

For a requested cross percentage \(p\), the desired RF + LR diagonal total is:

\[
W_{X,target} = \frac{p}{100}W_T
\]

The equal-and-opposite diagonal step is:

\[
D = \frac{W_{X,target}-W_X}{2}
\]

The target wheel loads are:

\[
\begin{aligned}
W_{LF,target} &= W_{LF}-D \\
W_{RF,target} &= W_{RF}+D \\
W_{LR,target} &= W_{LR}+D \\
W_{RR,target} &= W_{RR}-D
\end{aligned}
\]

This mathematical operation preserves vehicle total, front/rear totals, and left/right totals while changing the diagonal distribution. The displayed deltas are **desired changes in scale load**, not a direct number of coilover turns.

## CG-height calculation

The CG test uses:

- all four level corner weights;
- LF and RF weights after the rear axle is raised;
- wheelbase \(L\);
- level rear axle-centre height \(H_0\); and
- raised rear axle-centre height \(H_1\).

All weight measurements must share one unit. Wheelbase and both height measurements must share one length unit. The output uses the entered length unit.

Rear lift and chassis angle are:

\[
\Delta H = H_1-H_0
\]

\[
\theta = \sin^{-1}\left(\frac{\Delta H}{L}\right)
\]

The measured front-axle load change is:

\[
\Delta W_F = (W_{LF,raised}+W_{RF,raised})-(W_{LF}+W_{RF})
\]

The estimated CG height above the ground is:

\[
H_{CG} = H_0 + \frac{\Delta W_F L}{W_T\tan(\theta)}
\]

The app also reports sensitivity in length units per one weight unit of total front-axle change. A larger safe rear lift creates a larger measurable load shift and reduces the influence of scale resolution.

## Measurement workflow

### Prepare the car

1. Decide the exact configuration to tune: driver or equivalent ballast, fuel load, tyre pressures, fluids, and removable cargo.
2. Put the four scale pads on one flat plane. Verify and shim them rather than trusting the floor visually.
3. Confirm the controller channel for each physical pad. Swapping left/right or front/rear inputs produces plausible-looking but wrong results.
4. Zero the scales before loading the car.
5. Record ride heights and spring-perch positions before adjustment.

### Take repeatable readings

1. Centre the steering and keep the brakes released.
2. Load the car in the same way for every measurement.
3. Roll or use slip plates to release tyre and suspension bind, then settle the car consistently.
4. Repeat the reading. Investigate values that do not reproduce.
5. Enter the four stable readings and calculate.

### Adjust and verify

Increasing support or preload at one corner generally adds static load to that corner and its diagonal partner, while unloading the other diagonal. For example, increasing the LF corner tends to add load to LF and RR while removing load from RF and LR.

The change per spring-perch turn is vehicle-specific. Spring rates, motion ratios, suspension geometry, tyre friction, anti-roll-bar preload, and the platform all matter. Make a small change, settle the car again, re-weigh, and keep notes.

For a car that must turn in both directions, 50% cross is a common neutral starting point. Oval or asymmetric-course setups may deliberately use another value. The best target is established through controlled testing, temperatures, lap data, and driver feedback—not by a calculator alone.

## Rear-lift test safety

Raising a vehicle for a CG measurement can be hazardous.

- Work on a hard, level surface with sufficient overhead and surrounding clearance.
- Use lifting equipment, stands, ramps, platforms, wheel restraints, and scales rated for the load and geometry.
- Raise the rear symmetrically and keep the front tyres securely located on their scales.
- Use redundant support. Never rely on a hydraulic jack as the only support.
- Measure the rear **axle-centre height** before and after the lift.
- Keep people away from the fall zone and never work beneath an inadequately supported vehicle.
- Re-settle and repeat the measurement to assess reproducibility.

The reference method recommends a substantial rear lift; the app warns below 10 inches, 254 mm, or 25.4 cm. This is a measurement-quality notice, not permission to exceed the safe limits of your equipment or vehicle.

## Run on desktop

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install kivy==2.3.1
python main.py
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

The app opens in a phone-sized window on desktop for convenient development.

## Run the calculation self-tests

The self-tests cover balanced and unbalanced corner weights, preservation of axle/side totals, target diagonals, decimal parsing, and a known CG-height example. Kivy is not imported in this mode.

```bash
python main.py --self-test
```

Expected output:

```text
Corner Balance Lab: all calculation self-tests passed.
```

## Build an Android APK with Buildozer

Kivy recommends Buildozer as the easiest route to a full Android APK or AAB. The Android toolchain runs on Linux or macOS; Windows users can build through WSL2. Consult the current [Kivy Android packaging guide](https://kivy.org/doc/stable/guide/packaging-android.html) and [Buildozer installation instructions](https://buildozer.readthedocs.io/en/latest/installation/) before installing system dependencies.

### 1. Initialize the build configuration

From the folder containing `main.py`:

```bash
buildozer init
```

### 2. Edit `buildozer.spec`

At minimum, set or verify these values in the `[app]` section:

```ini
title = Corner Balance Lab
package.name = cornerbalancelab
package.domain = org.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version.regex = __version__ = ["'](.*)["']
version.filename = %(source.dir)s/main.py

requirements = python3,kivy==2.3.1
orientation = portrait
fullscreen = 0

# The app needs no Android permissions.
android.permissions =
```

Change `package.domain` to a domain or reverse-domain namespace you control before publishing.

### 3. Build a debug APK

```bash
buildozer -v android debug
```

The first build is slow because the Android SDK, NDK, and related tools are downloaded. The completed package is placed in `bin/`.

### 4. Deploy to a connected device

Enable Android developer mode and USB debugging, connect the device, and run:

```bash
buildozer android deploy run logcat
```

Or build, deploy, run, and show logs in one command:

```bash
buildozer -v android debug deploy run logcat
```

For a store release, follow the current Kivy, Buildozer, and Android documentation for release AAB creation, signing, target API level, privacy declarations, and store submission. Those requirements change over time.

## Session data

`SAVE SESSION` writes one file named `corner_balance_session.json` to Kivy's app-specific data directory. On Android this is private application storage. A new save replaces that file. No readings are transmitted.

The file contains:

- entered corner weights and units;
- target cross percentage;
- CG-test weights and geometry;
- schema version; and
- save time in UTC.

Calculated reports can be copied to the device clipboard for transfer into setup notes.

## Validation and error handling

The code rejects:

- blank, non-numeric, non-finite, zero, or negative wheel loads;
- target percentages outside 0–100%;
- targets that imply a zero or negative wheel load;
- rear heights that do not produce a positive lift;
- lift equal to or greater than wheelbase; and
- a rear-lift test that does not increase measured front-axle load.

A decimal comma is accepted when it is the only decimal separator. When a comma and a period both appear, commas are treated as grouping marks.

## Assumptions and limitations

- Corner weights are static measurements on a level scale plane.
- Target calculations assume ideal equal-and-opposite diagonal load transfer.
- The CG calculation treats the car as a rigid body in static equilibrium.
- Scale accuracy, platform level, tyre scrub, suspension friction, fuel movement, and inconsistent settling can dominate the result.
- The CG result is an estimate; repeat trials and report the spread.
- The app does not calculate roll centres, sprung-mass CG, lateral/longitudinal dynamic transfer, suspension kinematics, aero balance, tyre grip, or safe handling limits.
- A numerically balanced car is not automatically a safely handling car.

## Project structure

```text
car_corner_balance_android/
├── main.py      # Calculation engine, self-tests, Kivy UI, and local storage
└── README.md    # Documentation and Android build instructions
```

## Attribution

The formulas, terminology, and workshop workflow were developed from the three Rob Robinette pages linked at the top of this README. The implementation, validation, user interface, custom target support, session storage, reports, and self-tests are original to this project.

## Disclaimer

This software is for educational and setup-record purposes. It is not a substitute for a qualified motorsport engineer, vehicle manufacturer guidance, safe lifting practice, or controlled track testing. You are responsible for verifying measurements, equipment ratings, setup changes, and vehicle behaviour.
