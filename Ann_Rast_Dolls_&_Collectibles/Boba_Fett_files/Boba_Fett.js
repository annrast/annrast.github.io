// Created by iWeb 3.0.4 local-build-20250228

setTransparentGifURL('Media/transparent.gif');function applyEffects()
{var registry=IWCreateEffectRegistry();registry.registerEffects({stroke_0:new IWStrokeParts([{rect:new IWRect(-2,2,4,90),url:'Boba_Fett_files/stroke.png'},{rect:new IWRect(-2,-2,4,4),url:'Boba_Fett_files/stroke_1.png'},{rect:new IWRect(2,-2,150,4),url:'Boba_Fett_files/stroke_2.png'},{rect:new IWRect(152,-2,4,4),url:'Boba_Fett_files/stroke_3.png'},{rect:new IWRect(152,2,4,90),url:'Boba_Fett_files/stroke_4.png'},{rect:new IWRect(152,92,4,4),url:'Boba_Fett_files/stroke_5.png'},{rect:new IWRect(2,92,150,4),url:'Boba_Fett_files/stroke_6.png'},{rect:new IWRect(-2,92,4,4),url:'Boba_Fett_files/stroke_7.png'}],new IWSize(154,94))});registry.applyEffects();}
function hostedOnDM()
{return false;}
function onPageLoad()
{loadMozillaCSS('Boba_Fett_files/Boba_FettMoz.css')
adjustLineHeightIfTooBig('id1');adjustFontSizeIfTooBig('id1');adjustLineHeightIfTooBig('id2');adjustFontSizeIfTooBig('id2');adjustLineHeightIfTooBig('id3');adjustFontSizeIfTooBig('id3');adjustLineHeightIfTooBig('id4');adjustFontSizeIfTooBig('id4');Widget.onload();fixupAllIEPNGBGs();fixAllIEPNGs('Media/transparent.gif');applyEffects()}
function onPageUnload()
{Widget.onunload();}
