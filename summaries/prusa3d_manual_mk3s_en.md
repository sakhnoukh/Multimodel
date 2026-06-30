## Overview

This manual is the official user guide for the Original Prusa i3 MK3S+ and Original Prusa i3 MK3S+ Kit 3D printers. It provides comprehensive instructions for setup, calibration, operation, maintenance, and troubleshooting. The target audience includes new users, hobbyists, and professionals who own or are assembling these printers. The scope covers everything from initial unpacking and assembly (for kits) to advanced calibration, printing techniques, material handling, firmware updates, and common issue resolution.

The manual is structured to guide users through the entire lifecycle of printer ownership: from first-time setup and calibration to ongoing maintenance and advanced customization. It emphasizes safety, precision, and ease of use, leveraging Prusa’s open-source ethos and proprietary innovations like the SuperPINDA probe and mesh bed leveling. Users are directed to the official Prusa3D website for updated versions and translated manuals, and are encouraged to use the included LCD interface for most operations to ensure reliability and independence from external devices.

The handbook is version 3.17 (April 21, 2022), authored by Josef Prusa, the founder of Prusa Research, and includes detailed product specifications, safety guidelines, and step-by-step procedures. It assumes users have a basic understanding of 3D printing concepts but provides thorough explanations for calibration, troubleshooting, and advanced features. The manual also highlights the printer’s compatibility with 1.75mm filament and its support for various materials, including PLA, PETG, ABS, and composites.

---

## Quick Start Guide

1. **Read Safety Instructions** (Page 7) – Critical for preventing injury or damage.
2. **Place Printer on Stable Surface** (Page 10) – Ensure flat, dry, and draft-free environment.
3. **Install Drivers** (Page 47) – Download from Prusa3D website for Windows/macOS/Linux.
4. **Calibrate Printer** (Page 12) – Use the built-in Calibration Wizard or manual steps.
5. **Insert SD Card & Print** (Page 29) – Load a .gcode file and start printing.

---

## Key Sections Included

### 2. Product Details

- **Models Covered**: Original Prusa i3 MK3S+ (assembled) and MK3S+ Kit.
- **Filament**: Only 1.75mm diameter (not 2.85mm).
- **Manufacturer**: Prusa Research a.s., Prague, Czech Republic.
- **Power**: 90–135 VAC, 3.6A / 180–264 VAC, 1.8A (50–60 Hz).
- **Operating Environment**: Indoor only; 18°C–38°C, ≤85% humidity.
- **Weight**: Kit (gross/net): 9.8kg / 6.3kg; Assembled: 12kg / 6.3kg.
- **Serial Number**: Located on printer frame and packaging.

---

### 3. Introduction

- **Glossary**: Defines terms like “Bed,” “Extruder,” “Filament,” “Hotend,” and “1.75mm”.
- **Disclaimer**: Failure to follow instructions may cause injury or damage. User assumes all risks.
- **Safety Instructions** (Page 6–7):
  - Indoor use only.
  - Keep 30cm from objects; avoid moisture.
  - Do not touch nozzle or heatbed during operation (temperatures up to 300°C).
  - Never disassemble power supply.
  - Keep children away; never leave unattended.
  - Use in well-ventilated area due to plastic fumes.
- **Licenses**: Based on GNU GPL v3; open-source RepRap project. Modifications must be shared under same license.

---

### 4. Original Prusa i3 MK3S+ Printer

- **Description**: Fully assembled printer ready to print after calibration.
- **Key Components**:
  - Filament spool, spool holder, Z-axis, power supply, X-axis, heatbed with spring steel sheet, LCD panel, extruder, stepper motors.
- **Filament Compatibility**: Only 1.75mm filament. Do not use 2.85mm.

---

### 5. Original Prusa i3 MK3S+ Printer Kit

- **Contents**: Includes USB cable, acupuncture needle, glue stick, lubricant, tools, spare parts, IPA pads, test protocol.
- **Assembly**: Follow online manual at help.prusa3d.com (multilingual).
- **Assembly Time**: ~1 working day.

---

### 6. First Steps

#### 6.1 Printer Unpacking and Handling
- Hold upper frame; keep heatbed horizontal.
- Remove foam and zip-ties.
- Handle electronics carefully to avoid damage.

#### 6.2 Printer Assembly
- Follow online manual for kit users.
- Use provided tools and spare parts.

#### 6.3 Setup Before Printing
- Place printer on stable, draft-free surface.
- Attach filament holders and spool.
- Plug in power and check firmware (update if needed).

---

### 6.3.1 Calibration Flow and Wizard
- **Purpose**: Guides users through essential calibrations.
- **Steps**: Selftest, XYZ Calibration, Filament Loading, First Layer Calibration.
- **Manual Option**: Skip wizard and follow steps manually.
- **Note**: Disconnect USB during calibration to avoid host reset.

---

### 6.3.2 Preparation of the Spring Steel Sheet
- **Purpose**: Ensure optimal adhesion for prints.
- **Cleaning**: Use IPA, warm water + soap, or denatured alcohol (avoid acetone on powder-coated sheets).
- **Sheet Types**:
  - **Textured PEI**: Scratch-resistant, hides damage, may require brim for large prints.
  - **Smooth PEI**: Excellent adhesion for PLA, requires glue stick for Flex.
  - **Satin PEI**: Balanced adhesion for PLA/PETG, compatible with ASA, PC Blend.
- **Note**: Each sheet type requires individual first-layer calibration.

---

### 6.3.3 Increasing Adhesion
- **Methods**:
  - Use PrusaSlicer’s “Brim” option.
  - Apply glue stick for Nylon or Flex.
  - Use ABS juice for ABS (clean with acetone afterward).
- **Warning**: Do not use ABS juice on powder-coated steel sheets.

---

### 6.3.4 Selftest (Kit Only)
- **Purpose**: Diagnose assembly and wiring errors.
- **Tests**:
  - Extruder and fan.
  - Heatbed and hotend wiring.
  - XYZ motors and belts.
  - Endstops and filament sensor.
- **Error Handling**: Follow LCD prompts for resolution.

---

### 6.3.5 Calibrate XYZ (Kit Only)
- **Purpose**: Measure nozzle-to-probe distance and axis skew.
- **Steps**:
  - Use paper to check nozzle clearance.
  - Run calibration with/without steel sheet.
  - Verify axis perpendicularity (firmware corrects skew).
- **Error Handling**: Re-run if nozzle touches bed or probe fails.

---

### 6.3.6 Calibrate Z
- **Purpose**: Store Z-height reference points for mesh leveling.
- **When to Run**: After moving printer or after XYZ calibration.
- **Steps**:
  - Home X/Y axes.
  - Move Z to trigger SuperPINDA probe.
  - Clean nozzle before calibration.
- **Error Handling**: Re-run if nozzle debris interferes.

---

### 6.3.7 Mesh Bed Leveling
- **Purpose**: Create a virtual mesh of bed surface for precise leveling.
- **Settings**:
  - Default grid: 3x3 (9 points).
  - Upgrade to 7x7 for better accuracy (slower, but more precise).
  - Use “Magnets compensation” (recommended) to ignore readings near magnets.
- **Safety**: StallGuard prevents nozzle crashes.

---

### 6.3.8 Loading the Filament into the Extruder
- **Steps**:
  - Preheat nozzle (via LCD or manual).
  - Insert filament and confirm loading.
  - Extruder stepper automatically loads filament.
- **Note**: Z-axis rises if Z < 20mm to allow nozzle cleaning.

---

### 6.3.9 First Layer Calibration (Kit Only)
- **Purpose**: Adjust nozzle height for optimal first-layer adhesion.
- **Steps**:
  - Clean bed and ensure XYZ calibration is complete.
  - Print zig-zag pattern; adjust nozzle height live using knob.
  - Target: Slight squish, no contact with bed.
- **Advanced**: Bed level correction (±100 microns) for fine-tuning.

---

### 6.3.10 Fine Tuning the First Layer
- **Print Prusa Logo**: Test print to verify first-layer quality.
- **Live Adjust Z**: Adjust during printing for consistent results.
- **Check Probe Height**: If prints are inconsistent, lower probe slightly.

---

## Printer Control (Section 7)

### 7.2.1 LCD Screen
- Displays: Nozzle/bed temps, print progress, Z-axis position, speed, estimated time.

### 7.2.2 Controlling the LCD
- Use rotational knob to navigate; press to confirm.
- Reset button: Quick power toggle for troubleshooting.

### 7.2.3 Print Statistics
- Tracks filament usage and print time (lifetime or per print).

### 7.2.4 Fail Stats
- Logs failures: Filament runout, power panic, lost steps.

### 7.2.5 Normal vs. Stealth Mode
- **Normal