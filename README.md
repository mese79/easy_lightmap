Easy Light Map
==============

#### An addon for blender 2.7 to bake light map easily! ####
![panel](https://github.com/mese79/easy_lightmap/raw/master/shot1.png)

For baking your object light map to use in another engine like [three.js](http://threejs.org), first you have to add two uv layers and unwrap them. Then you must decide that do you want to bake diffuse color or object texture. if no then you have to un-check texture box and reset diffuse color into pure white color... . After baking was done you may want to revert your object material back to before baking state.

Well with this addon you can do all these steps just by one click!  
  

###### Changes in v0.2 ######
- There is no need to Imagemagick anymore.
- Bake process doesn't lock up UI and you can see baking progress.  
  

###### Note: ######
Since i couldn't find any way to get when baking process has been finished normally and when it has been cancelled by user, you have to save the baked image manually.

