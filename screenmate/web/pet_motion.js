const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
export function destination(command,W,H,size,protect){
 const margin=110*size/256+12,minY=Math.min(H-8,250*size/256+8);
 const positions={top_left:[0,0],top_right:[1,0],bottom_left:[0,1],bottom_right:[1,1],left:[0,.65],right:[1,.65],top:[.5,0],bottom:[.5,1]};
 const point=command.target==='coordinates'?[command.x,command.y]:positions[command.target];
 if(!point||point.some(n=>!Number.isFinite(n)))throw Error('invalid target');
 let x=clamp(point[0]*W,margin,W-margin),y=clamp(point[1]*H,minY,H-8),adjusted=false;
 if(protect&&x>.3*W-margin&&x<.7*W+margin){
  x=x<W/2?margin:W-margin;adjusted=true;
 }
 return {x,y,adjusted};
}
export function route(start,target,W,H,protect){
 if(!protect||(start.x<W/2)===(target.x<W/2))return [target];
 // Crossing sides goes along the bottom edge, rather than through the reticle.
 return [{x:start.x,y:H-8},{x:target.x,y:H-8},target];
}
