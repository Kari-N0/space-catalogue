// 2D cycle schematics for the engine explorer (Concept 002), one per engine id.
// Shapes carry data-part (one or more part node names, space-separated) so they
// highlight together with the 3D parts; explorer.css styles the stream classes
// (.ox .fu .pr .tg .og .el .xe .ion .ee .det .air .he .gas .gr .core .hw).
// Verbatim from the approved demo (js/main.js DIAGRAMS) — static first-party
// markup, injected with innerHTML by explorer/page.ts.

export const DIAGRAMS: Record<string, string> = {
  "pressure-fed": `
<svg class="ex-diagram" viewBox="0 0 300 160" role="img" aria-label="Pressure-fed cycle: helium pushes oxidizer and fuel from their tanks through the valves into the chamber. The fuel cools the chamber wall on its way to the injector.">
  <g class="pr" data-part="PF_HeliumTank"><circle cx="24" cy="80" r="15"/></g><text x="24" y="83" text-anchor="middle">He</text>
  <g class="hw" data-part="PF_PressureRegulator"><rect x="48" y="73" width="14" height="14" rx="2"/></g>
  <g class="pr" data-part="PF_PressurantLines"><path d="M39 80H48M62 80H74M74 80V38H92M74 80V122H92"/></g>
  <g class="ox" data-part="PF_TankOxidizer"><rect x="92" y="24" width="52" height="28" rx="14"/></g><text x="118" y="41" text-anchor="middle">Oxidizer</text>
  <g class="fu" data-part="PF_TankFuel"><rect x="92" y="108" width="52" height="28" rx="14"/></g><text x="118" y="125" text-anchor="middle">Fuel</text>
  <g class="ox" data-part="PF_FeedLineOxidizer"><path d="M144 38H164"/></g>
  <g class="hw" data-part="PF_ValveOxidizer"><path d="M164 32L176 44V32L164 44Z"/></g>
  <g class="ox" data-part="PF_InletLineOxidizer PF_OxidizerDome"><path d="M176 38H199V66"/></g>
  <g class="fu" data-part="PF_FeedLineFuel"><path d="M144 122H164"/></g>
  <g class="hw" data-part="PF_ValveFuel"><path d="M164 116L176 128V116L164 128Z"/></g>
  <g class="fu" data-part="PF_InletLineFuel PF_FuelManifold"><path d="M176 122H240V95"/></g>
  <g class="fu" data-part="PF_ChamberJacket" stroke-dasharray="3 2.5"><path d="M240 95L232 90L222 97H206M240 65L232 70L222 63H206"/></g>
  <g class="hw solid" data-part="PF_InjectorPlate"><rect x="196" y="66" width="6" height="28"/></g>
  <g class="hw" data-part="PF_ChamberLiner"><path d="M202 68H222L232 75L240 71M202 92H222L232 85L240 89"/></g>
  <g class="hw" data-part="PF_NozzleExtension"><path d="M240 71Q262 60 288 46M240 89Q262 100 288 114"/></g>
  <g class="gas"><path d="M208 80H280M273 75L280 80L273 85"/></g>
</svg>`,
  "gas-generator": `
<svg class="ex-diagram" viewBox="0 0 300 170" role="img" aria-label="Gas-generator cycle: two pumps on one shaft raise the propellant pressure. A small gas generator burns a little of both propellants to drive the turbine, and its exhaust is dumped overboard. The fuel cools the nozzle and chamber on its way to the injector.">
  <g class="ox" data-part="GG_TankOxidizer"><rect x="8" y="20" width="48" height="26" rx="13"/></g><text x="32" y="36" text-anchor="middle">Oxidizer</text>
  <g class="fu" data-part="GG_TankFuel"><rect x="8" y="118" width="48" height="26" rx="13"/></g><text x="32" y="134" text-anchor="middle">Fuel</text>
  <g class="ox" data-part="GG_FeedLineOxidizer"><path d="M56 33H98"/></g>
  <g class="fu" data-part="GG_FeedLineFuel"><path d="M56 131H98"/></g>
  <g class="hw" data-part="GG_PumpOxidizer"><circle cx="110" cy="33" r="12"/></g>
  <g class="hw" data-part="GG_PumpFuel"><circle cx="110" cy="131" r="12"/></g>
  <g class="hw" data-part="GG_PumpRotor"><path d="M110 45V72M110 92V119"/></g>
  <g class="hw" data-part="GG_Turbine"><path d="M101 74L119 70V94L101 90Z"/></g>
  <g class="ox" data-part="GG_ValveOxidizer GG_InletLineOxidizer GG_OxidizerDome"><path d="M122 33H150M162 33H189V66"/></g>
  <g class="hw" data-part="GG_ValveOxidizer"><path d="M150 27L162 39V27L150 39Z"/></g>
  <g class="fu" data-part="GG_InletLineFuel GG_FuelManifold"><path d="M122 131H150M162 131H270V112"/></g>
  <g class="hw" data-part="GG_ValveFuel"><path d="M150 125L162 137V125L150 137Z"/></g>
  <g class="fu" data-part="GG_Nozzle GG_ChamberJacket" stroke-dasharray="3 2.5"><path d="M270 112Q250 102 231 94L222 89L212 97H196"/></g>
  <g class="ox" data-part="GG_TapOxidizer"><path d="M136 33V64Q136 74 144 78"/></g>
  <g class="fu" data-part="GG_TapFuel"><path d="M136 131V100Q136 90 144 86"/></g>
  <g class="tg" data-part="GG_GasGenerator"><circle cx="152" cy="82" r="9"/><path d="M143 82H119"/></g><text x="152" y="85" text-anchor="middle">GG</text>
  <g class="tg" data-part="GG_TurbineExhaust"><path d="M101 82H80V160M75 153L80 160L85 153"/></g>
  <g class="hw solid" data-part="GG_Injector"><rect x="186" y="66" width="6" height="28"/></g>
  <g class="hw" data-part="GG_ChamberLiner"><path d="M192 68H212L222 75L230 71M192 92H212L222 85L230 89"/></g>
  <g class="hw" data-part="GG_Nozzle"><path d="M230 71Q254 60 290 44M230 89Q254 100 290 116"/></g>
  <g class="gas"><path d="M198 80H284M277 75L284 80L277 85"/></g>
</svg>`,
  "staged-combustion": `
<svg class="ex-diagram" viewBox="0 0 300 172" role="img" aria-label="Staged-combustion cycle: the fuel cools the nozzle and chamber, then burns with a little oxygen in two preburners. That gas drives the two pump turbines and then flows into the main chamber, where it burns with the rest of the oxygen.">
  <g class="ox" data-part="SC_TankOxidizer"><rect x="8" y="20" width="48" height="26" rx="13"/></g><text x="32" y="36" text-anchor="middle">Oxidizer</text>
  <g class="fu" data-part="SC_TankFuel"><rect x="8" y="118" width="48" height="26" rx="13"/></g><text x="32" y="134" text-anchor="middle">Fuel</text>
  <g class="ox" data-part="SC_FeedLineOxidizer"><path d="M56 33H72"/></g>
  <g class="fu" data-part="SC_FeedLineFuel"><path d="M56 131H72"/></g>
  <g class="hw" data-part="SC_PumpOxidizer"><circle cx="84" cy="33" r="12"/></g>
  <g class="hw" data-part="SC_PumpFuel"><circle cx="84" cy="131" r="12"/></g>
  <g class="hw" data-part="SC_RotorOxidizer"><path d="M96 33H101"/></g>
  <g class="hw" data-part="SC_RotorFuel"><path d="M96 131H101"/></g>
  <g class="hw" data-part="SC_TurbineOxidizer"><path d="M101 26L116 22V44L101 40Z"/></g>
  <g class="hw" data-part="SC_TurbineFuel"><path d="M101 124L116 120V142L101 138Z"/></g>
  <g class="tg" data-part="SC_PreburnerOxidizer"><circle cx="132" cy="33" r="8"/><path d="M124 33H116"/></g>
  <g class="tg" data-part="SC_PreburnerFuel"><circle cx="132" cy="131" r="8"/><path d="M124 131H116"/></g>
  <g class="tg" data-part="SC_HotGasManifold"><path d="M108 43V72H186M108 121V88H186"/></g>
  <g class="ox" data-part="SC_ValveOxidizer SC_InletLineOxidizer SC_OxidizerDome"><path d="M84 21V10H150M162 10H189V66"/></g>
  <g class="hw" data-part="SC_ValveOxidizer"><path d="M150 4L162 16V4L150 16Z"/></g>
  <g class="ox" data-part="SC_PreburnerOxidizerLines"><path d="M132 10V25M172 10V131H140"/></g>
  <g class="fu" data-part="SC_ValveFuel SC_CoolantFeedLine SC_FuelManifold"><path d="M84 143V160H150M162 160H270V112"/></g>
  <g class="hw" data-part="SC_ValveFuel"><path d="M150 154L162 166V154L150 166Z"/></g>
  <g class="fu" data-part="SC_Nozzle SC_ChamberJacket" stroke-dasharray="3 2.5"><path d="M270 112Q250 102 231 94L222 89L212 97H198"/></g>
  <g class="fu" data-part="SC_CoolantCollector SC_PreburnerFuelLines"><path d="M198 97V110H132V123M156 110V33H140"/></g>
  <g class="hw solid" data-part="SC_Injector"><rect x="186" y="66" width="6" height="28"/></g>
  <g class="hw" data-part="SC_ChamberLiner"><path d="M192 68H212L222 75L230 71M192 92H212L222 85L230 89"/></g>
  <g class="hw" data-part="SC_Nozzle"><path d="M230 71Q254 60 290 44M230 89Q254 100 290 116"/></g>
  <g class="gas"><path d="M198 80H284M277 75L284 80L277 85"/></g>
</svg>`,
  "full-flow": `
<svg class="ex-diagram" viewBox="0 0 300 172" role="img" aria-label="Full-flow staged-combustion cycle: nearly all the oxygen burns with a little fuel in one preburner, and nearly all the fuel burns with a little oxygen in the other. Each hot gas drives its own pump turbine, then both flow into the main chamber and burn together.">
  <g class="ox" data-part="FF_TankOxidizer"><rect x="8" y="20" width="48" height="26" rx="13"/></g><text x="32" y="36" text-anchor="middle">Oxidizer</text>
  <g class="fu" data-part="FF_TankFuel"><rect x="8" y="118" width="48" height="26" rx="13"/></g><text x="32" y="134" text-anchor="middle">Fuel</text>
  <g class="ox" data-part="FF_FeedLineOxidizer"><path d="M56 33H72"/></g>
  <g class="fu" data-part="FF_FeedLineFuel"><path d="M56 131H72"/></g>
  <g class="hw" data-part="FF_PumpOxidizer"><circle cx="84" cy="33" r="12"/></g>
  <g class="hw" data-part="FF_PumpFuel"><circle cx="84" cy="131" r="12"/></g>
  <g class="hw" data-part="FF_RotorOxidizer"><path d="M96 33H101"/></g>
  <g class="hw" data-part="FF_RotorFuel"><path d="M96 131H101"/></g>
  <g class="hw" data-part="FF_TurbineOxidizer"><path d="M101 26L116 22V44L101 40Z"/></g>
  <g class="hw" data-part="FF_TurbineFuel"><path d="M101 124L116 120V142L101 138Z"/></g>
  <g class="og" data-part="FF_PreburnerOxidizer"><circle cx="132" cy="33" r="8"/><path d="M124 33H116"/></g>
  <g class="tg" data-part="FF_PreburnerFuel"><circle cx="132" cy="131" r="8"/><path d="M124 131H116"/></g>
  <g class="og" data-part="FF_OxidizerDome"><path d="M108 43V58H189V66"/></g>
  <g class="tg" data-part="FF_FuelGasManifold"><path d="M108 121V88H186"/></g>
  <g class="ox" data-part="FF_ValveOxidizer FF_OxidizerLine"><path d="M84 21V10H100M112 10H132V25"/></g>
  <g class="hw" data-part="FF_ValveOxidizer"><path d="M100 4L112 16V4L100 16Z"/></g>
  <g class="ox" data-part="FF_PreburnerOxidizerLine"><path d="M132 10H172V131H140"/></g>
  <g class="fu" data-part="FF_ValveFuel FF_CoolantFeedLine FF_FuelManifold"><path d="M84 143V160H150M162 160H270V112"/></g>
  <g class="hw" data-part="FF_ValveFuel"><path d="M150 154L162 166V154L150 166Z"/></g>
  <g class="fu" data-part="FF_Nozzle FF_ChamberJacket" stroke-dasharray="3 2.5"><path d="M270 112Q250 102 231 94L222 89L212 97H198"/></g>
  <g class="fu" data-part="FF_CoolantCollector FF_PreburnerFuelLine"><path d="M198 97V110H132V123"/></g>
  <g class="fu" data-part="FF_PreburnerFuelTap"><path d="M156 110V33H140"/></g>
  <g class="hw solid" data-part="FF_Injector"><rect x="186" y="66" width="6" height="28"/></g>
  <g class="hw" data-part="FF_ChamberLiner"><path d="M192 68H212L222 75L230 71M192 92H212L222 85L230 89"/></g>
  <g class="hw" data-part="FF_Nozzle"><path d="M230 71Q254 60 290 44M230 89Q254 100 290 116"/></g>
  <g class="gas"><path d="M198 80H284M277 75L284 80L277 85"/></g>
</svg>`,
  expander: `
<svg class="ex-diagram" viewBox="0 0 300 172" role="img" aria-label="Expander cycle: liquid hydrogen is pumped through the tube wall of the chamber and nozzle, where the engine's heat turns it into gas. The gas drives the turbine and then burns in the chamber. One turbine drives both pumps through a gearbox, and nothing burns outside the main chamber.">
  <g class="ox" data-part="EX_TankOxidizer"><rect x="8" y="20" width="48" height="26" rx="13"/></g><text x="32" y="36" text-anchor="middle">Oxidizer</text>
  <g class="fu" data-part="EX_TankFuel"><rect x="8" y="118" width="48" height="26" rx="13"/></g><text x="32" y="134" text-anchor="middle">Fuel</text>
  <g class="ox" data-part="EX_FeedLineOxidizer"><path d="M56 33H72"/></g>
  <g class="fu" data-part="EX_FeedLineFuel"><path d="M56 131H72"/></g>
  <g class="hw" data-part="EX_PumpOxidizer"><circle cx="84" cy="33" r="12"/></g>
  <g class="hw" data-part="EX_PumpFuel"><circle cx="84" cy="131" r="12"/></g>
  <g class="hw" data-part="EX_Gearbox EX_RotorOxidizer" stroke-dasharray="2 3"><path d="M84 45V119"/></g>
  <g class="hw" data-part="EX_RotorFuel"><path d="M96 131H101"/></g>
  <g class="hw" data-part="EX_Turbine"><path d="M101 124L116 120V142L101 138Z"/></g>
  <g class="ox" data-part="EX_ValveOxidizer EX_InletLineOxidizer EX_OxidizerDome"><path d="M96 33H150M162 33H189V66"/></g>
  <g class="hw" data-part="EX_ValveOxidizer"><path d="M150 27L162 39V27L150 39Z"/></g>
  <g class="fu" data-part="EX_CoolantFeedLine EX_FuelManifold"><path d="M84 143V160H256V104"/></g>
  <g class="fu" data-part="EX_TubeWall" stroke-dasharray="3 2.5"><path d="M256 104Q242 98 231 94L222 89L212 97H198"/></g>
  <g class="fu" data-part="EX_CoolantCollector EX_TurbineInletLine"><path d="M198 97V108H132V131H116"/></g>
  <g class="fu" data-part="EX_TurbineOutletLine EX_InjectorManifold"><path d="M108 121V86H150M162 86H186"/></g>
  <g class="hw" data-part="EX_ValveFuel"><path d="M150 80L162 92V80L150 92Z"/></g>
  <g class="hw solid" data-part="EX_InjectorPlate"><rect x="186" y="66" width="6" height="28"/></g>
  <g class="hw" data-part="EX_TubeWall"><path d="M192 68H212L222 75L230 71Q242 65.5 256 59M192 92H212L222 85L230 89Q242 94.5 256 101"/></g>
  <g class="hw" data-part="EX_NozzleExtension"><path d="M256 59Q272 52 290 44M256 101Q272 108 290 116"/></g>
  <g class="gas"><path d="M198 80H284M277 75L284 80L277 85"/></g>
</svg>`,
  "electric-pump": `
<svg class="ex-diagram" viewBox="0 0 300 172" role="img" aria-label="Electric pump-fed cycle: a battery powers two electric motors, and each motor drives one pump. There is no turbine and no hot gas in the pump drive. The fuel cools the nozzle and chamber on its way to the injector.">
  <g class="ox" data-part="EP_TankOxidizer"><rect x="8" y="20" width="48" height="26" rx="13"/></g><text x="32" y="36" text-anchor="middle">Oxidizer</text>
  <g class="fu" data-part="EP_TankFuel"><rect x="8" y="118" width="48" height="26" rx="13"/></g><text x="32" y="134" text-anchor="middle">Fuel</text>
  <g class="ox" data-part="EP_FeedLineOxidizer"><path d="M56 33H72"/></g>
  <g class="fu" data-part="EP_FeedLineFuel"><path d="M56 131H72"/></g>
  <g class="hw" data-part="EP_PumpOxidizer"><circle cx="84" cy="33" r="12"/></g>
  <g class="hw" data-part="EP_PumpFuel"><circle cx="84" cy="131" r="12"/></g>
  <g class="hw" data-part="EP_RotorOxidizer"><path d="M96 33H102"/></g>
  <g class="hw" data-part="EP_RotorFuel"><path d="M96 131H102"/></g>
  <g class="hw" data-part="EP_MotorOxidizer EP_InverterOxidizer"><rect x="102" y="23" width="20" height="20" rx="3"/></g><text x="112" y="36" text-anchor="middle">M</text>
  <g class="hw" data-part="EP_MotorFuel EP_InverterFuel"><rect x="102" y="121" width="20" height="20" rx="3"/></g><text x="112" y="134" text-anchor="middle">M</text>
  <g class="el" data-part="EP_Battery"><rect x="96" y="68" width="32" height="28" rx="3"/></g><text x="112" y="85" text-anchor="middle">Batt.</text>
  <g class="el" data-part="EP_CableOxidizer"><path d="M112 68V43"/></g>
  <g class="el" data-part="EP_CableFuel"><path d="M112 96V121"/></g>
  <g class="ox" data-part="EP_ValveOxidizer EP_InletLineOxidizer EP_OxidizerDome"><path d="M84 21V10H150M162 10H189V66"/></g>
  <g class="hw" data-part="EP_ValveOxidizer"><path d="M150 4L162 16V4L150 16Z"/></g>
  <g class="fu" data-part="EP_ValveFuel EP_InletLineFuel EP_FuelManifold"><path d="M84 143V160H150M162 160H262V108"/></g>
  <g class="hw" data-part="EP_ValveFuel"><path d="M150 154L162 166V154L150 166Z"/></g>
  <g class="fu" data-part="EP_Nozzle EP_ChamberJacket" stroke-dasharray="3 2.5"><path d="M262 108Q246 100 231 94L222 89L212 97H196"/></g>
  <g class="hw solid" data-part="EP_InjectorPlate"><rect x="186" y="66" width="6" height="28"/></g>
  <g class="hw" data-part="EP_ChamberLiner"><path d="M192 68H212L222 75L230 71M192 92H212L222 85L230 89"/></g>
  <g class="hw" data-part="EP_Nozzle"><path d="M230 71Q254 60 290 44M230 89Q254 100 290 116"/></g>
  <g class="gas"><path d="M198 80H284M277 75L284 80L277 85"/></g>
</svg>`,
  solid: `
<svg class="ex-diagram" viewBox="0 0 300 150" role="img" aria-label="Solid motor in section: the case is filled with a solid propellant grain with a hollow bore down its centre. An igniter at the front lights the bore surface, the gas flows down the bore and leaves through the nozzle.">
  <g class="hw" data-part="SM_AttachRing"><path d="M74 22H46M74 128H46"/></g>
  <g class="hw" data-part="SM_Case"><rect x="40" y="28" width="150" height="94" rx="45"/></g>
  <g class="gr" data-part="SM_Grain SM_Insulation"><path d="M88 34H146Q184 34 184 62V66L150 60L66 72V60Q66 34 88 34ZM88 116H146Q184 116 184 88V84L150 90L66 78V90Q66 116 88 116Z"/></g>
  <text x="118" y="50" text-anchor="middle">Solid propellant</text>
  <g class="hw solid" data-part="SM_Igniter"><rect x="34" y="71" width="30" height="8"/></g>
  <g class="hw" data-part="SM_SafeArm"><rect x="25" y="67" width="9" height="16" rx="2"/></g>
  <g class="hw" data-part="SM_Throat"><path d="M186 64L204 71L212 69M186 86L204 79L212 81"/></g>
  <g class="hw" data-part="SM_ExitCone"><path d="M212 69L282 42M212 81L282 108"/></g>
  <g class="gas"><path d="M90 75H272M265 70L272 75L265 80"/></g>
</svg>`,
  hybrid: `
<svg class="ex-diagram" viewBox="0 0 300 150" role="img" aria-label="Hybrid motor in section: a tank of liquid oxidizer feeds through one valve and an injector into a case that holds a solid fuel grain. The fuel burns along its central port and the gas leaves through the nozzle.">
  <g class="ox" data-part="HY_OxidizerTank"><rect x="8" y="42" width="78" height="66" rx="33"/></g><text x="47" y="78" text-anchor="middle">Oxidizer</text>
  <g class="hw" data-part="HY_ThrustFlange"><path d="M47 38V34M47 112V116"/></g>
  <g class="ox" data-part="HY_ValveOxidizer"><path d="M86 75H98M110 75H120"/></g>
  <g class="hw" data-part="HY_ValveOxidizer"><path d="M98 69L110 81V69L98 81Z"/></g>
  <g class="hw" data-part="HY_ThrustSkirt" stroke-dasharray="2 3"><path d="M78 50L120 46M78 100L120 104"/></g>
  <g class="hw solid" data-part="HY_Injector"><rect x="120" y="50" width="5" height="50"/></g>
  <g class="hw" data-part="HY_Case"><path d="M125 46H222L232 56M125 104H222L232 94"/></g>
  <g class="gr" data-part="HY_Grain HY_Insulation"><path d="M136 50H218V66H136ZM136 84H218V100H136Z"/></g>
  <text x="177" y="61" text-anchor="middle">Solid fuel</text>
  <g class="hw" data-part="HY_Throat"><path d="M232 56L240 70L246 68M232 94L240 80L246 82"/></g>
  <g class="hw" data-part="HY_ExitCone"><path d="M246 68L290 50M246 82L290 100"/></g>
  <g class="gas"><path d="M150 75H282M275 70L282 75L275 80"/></g>
</svg>`,
  ion: `
<svg class="ex-diagram" viewBox="0 0 300 150" role="img" aria-label="Gridded ion thruster: xenon gas enters a chamber where a cathode's electrons ionise it. Two grids at high voltage accelerate the ions into a beam, and a neutralizer adds electrons to the beam. A power unit supplies the voltages.">
  <g class="xe" data-part="IT_XenonTank"><circle cx="24" cy="48" r="16"/></g><text x="24" y="51" text-anchor="middle">Xe</text>
  <g class="xe" data-part="IT_FlowController IT_PropellantManifold"><path d="M40 48H96V62"/></g>
  <g class="el" data-part="IT_PowerUnit"><rect x="8" y="96" width="38" height="26" rx="3"/></g><text x="27" y="112" text-anchor="middle">Power</text>
  <g class="el" data-part="IT_Harness"><path d="M46 104H84V88M46 114H150V128H196"/></g>
  <g class="hw" data-part="IT_DischargeChamber IT_PlasmaScreen"><path d="M84 62H176M84 88H176M84 62V88"/></g>
  <g class="hw" data-part="IT_Magnets" stroke-dasharray="4 6"><path d="M92 58H170M92 92H170"/></g>
  <g class="hw solid" data-part="IT_DischargeCathode"><rect x="84" y="71" width="16" height="8"/></g>
  <g class="hw" data-part="IT_ScreenGrid" stroke-dasharray="3 3"><path d="M176 58V92"/></g>
  <g class="hw" data-part="IT_AcceleratorGrid" stroke-dasharray="3 3"><path d="M183 56V94"/></g>
  <g class="ion"><path d="M186 66H284M186 75H290M186 84H284M283 71L290 75L283 79"/></g>
  <g class="hw solid" data-part="IT_Neutralizer"><rect x="196" y="122" width="14" height="10"/></g>
  <g class="ee" data-part="IT_Neutralizer"><path d="M210 124Q232 112 246 90"/></g>
  <text x="130" y="78" text-anchor="middle">Ionise</text>
</svg>`,
  aerospike: `
<svg class="ex-diagram" viewBox="0 0 300 150" role="img" aria-label="Linear aerospike in section: two rows of small thrust cells fire along the outside of a wedge-shaped ramp. The exhaust is contained by the ramp on one side and by the surrounding air on the other. Pumps sit inside the wedge, and turbine gas is bled out through its flat base.">
  <g class="hw" data-part="AS_ThrustFrame"><path d="M70 20V130"/></g>
  <g class="hw" data-part="AS_RampRight"><path d="M112 28Q170 44 232 62"/></g>
  <g class="hw" data-part="AS_RampLeft"><path d="M112 122Q170 106 232 88"/></g>
  <g class="hw" data-part="AS_BasePlate"><path d="M232 62V88"/></g>
  <g class="hw solid" data-part="AS_ThrustCellsRight"><rect x="88" y="14" width="24" height="12" rx="3" transform="rotate(14 100 20)"/></g>
  <g class="hw solid" data-part="AS_ThrustCellsLeft"><rect x="88" y="124" width="24" height="12" rx="3" transform="rotate(-14 100 130)"/></g>
  <g class="hw" data-part="AS_PumpFuel AS_TurbineFuel AS_RotorFuel"><circle cx="118" cy="62" r="10"/></g>
  <g class="hw" data-part="AS_PumpOxidizer AS_TurbineOxidizer AS_RotorOxidizer"><circle cx="118" cy="88" r="10"/></g>
  <g class="tg" data-part="AS_GasGenerator AS_TurbineDucts"><circle cx="150" cy="75" r="7"/><path d="M143 72L128 66M143 78L128 84M157 75H228"/></g>
  <g class="fu" data-part="AS_FuelLines AS_ManifoldFuelRight AS_ManifoldFuelLeft"><path d="M112 54L100 30M112 96L100 120" stroke-dasharray="3 2.5"/></g>
  <g class="gas"><path d="M116 20Q176 36 262 60M255 54L262 60L253 62M116 130Q176 114 262 90M255 96L262 90L253 88"/></g>
  <g class="tg"><path d="M236 75H262M256 71L262 75L256 79"/></g>
  <text x="182" y="28" text-anchor="middle">Open to the air</text>
</svg>`,
  "rotating-detonation": `
<svg class="ex-diagram" viewBox="0 0 300 150" role="img" aria-label="Rotating detonation engine: on the left, the ring-shaped channel seen end-on, with two detonation waves travelling around it. On the right, a side section: propellant enters the thin channel from the injector, the wave burns it, and the gas leaves along the tapered centre body.">
  <g class="hw" data-part="RD_OuterBody"><circle cx="62" cy="75" r="44"/></g>
  <g class="hw" data-part="RD_CenterBody"><circle cx="62" cy="75" r="32"/></g>
  <g class="det"><path d="M62 37A38 38 0 0 1 97 60M97.7 51L97 60L90 54.4M62 113A38 38 0 0 1 27 90M26.3 99L27 90L34 95.6"/></g>
  <text x="62" y="78" text-anchor="middle">Waves</text>
  <g class="hw solid" data-part="RD_InjectorRing RD_InjectorHead"><rect x="140" y="30" width="8" height="90"/></g>
  <g class="ox" data-part="RD_InletLineOxidizer RD_ValveOxidizer"><path d="M126 44H140"/></g>
  <g class="fu" data-part="RD_InletLineFuel RD_ValveFuel"><path d="M126 106H140"/></g>
  <g class="hw" data-part="RD_OuterBody"><path d="M148 30H212M148 120H212"/></g>
  <g class="hw" data-part="RD_CenterBody"><path d="M148 44H206Q250 62 272 75Q250 88 206 106H148"/></g>
  <g class="det"><path d="M160 32V42M160 108V118"/></g>
  <g class="gas"><path d="M168 37H214Q254 50 286 62M279 56L286 62L277 64M168 113H214Q254 100 286 88M279 94L286 88L277 86"/></g>
</svg>`,
  "nuclear-thermal": `
<svg class="ex-diagram" viewBox="0 0 300 172" role="img" aria-label="Nuclear thermal cycle: liquid hydrogen is pumped through the nozzle wall and the reflector, then down through the reactor core, where it is heated. It leaves through the nozzle. A little hot hydrogen is bled off to drive the pump turbine and is dumped overboard.">
  <g class="fu" data-part="NT_TankFuel"><rect x="8" y="24" width="52" height="28" rx="14"/></g><text x="34" y="41" text-anchor="middle">Hydrogen</text>
  <g class="fu" data-part="NT_FeedLine"><path d="M60 38H78"/></g>
  <g class="hw" data-part="NT_Pump"><circle cx="90" cy="38" r="12"/></g>
  <g class="hw" data-part="NT_PumpRotor"><path d="M90 50V60"/></g>
  <g class="hw" data-part="NT_Turbine"><path d="M82 60H98L102 76H78Z"/></g>
  <g class="fu" data-part="NT_ValveFuel NT_CoolantFeedLine NT_CoolantManifold"><path d="M102 38H120M132 38H262V58"/></g>
  <g class="hw" data-part="NT_ValveFuel"><path d="M120 32L132 44V32L120 44Z"/></g>
  <g class="fu" data-part="NT_Nozzle NT_Reflector" stroke-dasharray="3 2.5"><path d="M262 58Q244 66 226 72L218 78H140V96"/></g>
  <g class="hw" data-part="NT_PressureVessel"><rect x="134" y="74" width="80" height="52" rx="4"/></g>
  <g class="hw" data-part="NT_Reflector NT_ControlDrums"><path d="M146 82H206M146 118H206"/></g>
  <g class="core" data-part="NT_ReactorCore"><rect x="150" y="88" width="52" height="24"/><path d="M160 88V112M170 88V112M180 88V112M190 88V112"/></g>
  <text x="176" y="103" text-anchor="middle">Reactor</text>
  <g class="hw" data-part="NT_Nozzle"><path d="M214 84L226 96L232 92Q256 82 290 68M214 116L226 104L232 108Q256 118 290 132"/></g>
  <g class="gas"><path d="M206 100H284M277 95L284 100L277 105"/></g>
  <g class="tg" data-part="NT_BleedLine"><path d="M210 122V150H112V68H102"/></g>
  <g class="tg" data-part="NT_TurbineExhaust"><path d="M78 68H64V160M59 153L64 160L69 153"/></g>
</svg>`,
  "air-breathing": `
<svg class="ex-diagram" viewBox="0 0 300 172" role="img" aria-label="Air-breathing rocket cycle: air enters the intake and is chilled in the precooler, compressed, and burned with hydrogen in the rocket chambers. A closed helium loop carries the heat from the precooler through a turbine that drives the compressor, and then gives the heat to the cold hydrogen. In rocket mode liquid oxygen replaces the air.">
  <g class="hw" data-part="AB_NacelleUpper AB_NacelleLower"><path d="M30 34H250M30 138H250"/></g>
  <g class="hw" data-part="AB_IntakeCone"><path d="M8 86L52 70V102Z"/></g>
  <g class="air"><path d="M4 52H40L60 60M4 120H40L60 112"/></g>
  <g class="hw" data-part="AB_Precooler"><rect x="60" y="52" width="26" height="68"/><path d="M66 52V120M73 52V120M80 52V120"/></g><text x="73" y="46" text-anchor="middle">Precooler</text>
  <g class="air"><path d="M86 86H104"/></g>
  <g class="hw" data-part="AB_Compressor"><path d="M104 72L124 78V94L104 100Z"/></g>
  <g class="hw" data-part="AB_CompressorRotor"><path d="M124 86H134"/></g>
  <g class="he" data-part="AB_CompressorRotor"><path d="M134 78L146 74V98L134 94Z"/></g>
  <g class="air"><path d="M124 80Q150 60 196 76"/></g>
  <g class="he" data-part="AB_HeliumLoop AB_HeliumCirculator"><path d="M73 52V40H140V74M140 98V112H170M186 112H196V152H73V120"/></g>
  <g class="hw" data-part="AB_HeatExchanger AB_Preburner"><rect x="170" y="104" width="16" height="16"/></g>
  <g class="fu" data-part="AB_TankFuel AB_PumpFuel AB_FuelLine"><path d="M178 164V120M178 104V92H196"/></g><text x="196" y="167">Hydrogen</text>
  <g class="ox" data-part="AB_TankOxidizer AB_PumpOxidizer AB_OxidizerManifold" stroke-dasharray="3 2.5"><path d="M178 8V68H196"/></g><text x="184" y="14">Oxygen, rocket mode</text>
  <g class="hw solid" data-part="AB_ThrustChambers"><rect x="196" y="64" width="6" height="44"/></g>
  <g class="hw" data-part="AB_ThrustChambers"><path d="M202 68H214L222 76L228 73Q250 66 284 54M202 104H214L222 96L228 99Q250 106 284 118"/></g>
  <g class="gas"><path d="M208 86H280M273 81L280 86L273 91"/></g>
</svg>`,
};
