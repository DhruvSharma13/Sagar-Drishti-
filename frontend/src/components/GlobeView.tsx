import React, { useEffect, useRef, useState } from 'react';
import * as Cesium from 'cesium';
import { FloatProfile, GliderTrack, OceanGridPoint } from '../types/ocean';
import { AlertCircle, Compass, Radio, RotateCcw } from 'lucide-react';

interface GlobeViewProps {
  floats: FloatProfile[];
  gliders: GliderTrack[];
  gridPoints: OceanGridPoint[];
  selectedFloat: FloatProfile | null;
  onSelectFloat: (float: FloatProfile | null) => void;
  onResetView?: () => void;
  showGliders: boolean;
  showHeatmap: boolean;
  variable: string;
  maxDepth: number;
}

const DEFAULT_CAMERA_DESTINATION = Cesium.Cartesian3.fromDegrees(78.0, 12.0, 6500000.0);

// Helper function for Heatmap surface grid coloring
const getHeatmapColor = (variable: string, val: number): string => {
  if (variable === 'temperature') {
    // Temperature color scale (°C)
    if (val < 18) return '#1d4ed8'; // Deep Blue
    if (val < 22) return '#0284c7'; // Sky Blue
    if (val < 25) return '#06b6d4'; // Cyan
    if (val < 27) return '#eab308'; // Yellow
    if (val < 28.5) return '#f97316'; // Orange
    return '#ef4444'; // Red
  } else if (variable === 'salinity') {
    // Salinity color scale (PSU)
    if (val < 33.5) return '#10b981'; // Emerald (low salinity / freshwater)
    if (val < 34.5) return '#06b6d4'; // Cyan
    if (val < 35.5) return '#3b82f6'; // Blue
    if (val < 36.0) return '#8b5cf6'; // Violet
    return '#d946ef'; // Magenta (high salinity / evaporation)
  } else if (variable === 'chlorophyll') {
    // Chlorophyll-a color scale (mg/m³)
    if (val < 0.1) return '#0369a1'; // Dark Ocean Blue
    if (val < 0.3) return '#14b8a6'; // Teal
    if (val < 0.6) return '#22c55e'; // Seafoam Green
    if (val < 0.9) return '#84cc16'; // Lime
    return '#10b981'; // Bright Emerald Green
  }
  return '#06b6d4';
};

export const GlobeView: React.FC<GlobeViewProps> = ({
  floats,
  gliders,
  gridPoints,
  selectedFloat,
  onSelectFloat,
  onResetView,
  showGliders,
  showHeatmap,
  variable,
  maxDepth
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);

  // Helper to fly camera back to full globe
  const handleResetCamera = () => {
    console.log('Reset View clicked');
    const viewer = viewerRef.current;
    if (viewer && !viewer.isDestroyed()) {
      const targetDestination = Cesium.Cartesian3.fromDegrees(78.0, 12.0, 6500000.0);
      console.log('Camera flyTo destination:', targetDestination);
      viewer.camera.flyTo({
        destination: targetDestination,
        orientation: {
          heading: Cesium.Math.toRadians(0.0),
          pitch: Cesium.Math.toRadians(-80.0),
          roll: 0.0
        },
        duration: 1.5
      });
    }
    if (onResetView) {
      onResetView();
    }
  };

  // Initialize Cesium 3D Globe with Free OpenStreetMap Imagery
  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return;

    // Use zero-token free imagery & terrain
    Cesium.Ion.defaultAccessToken = '';

    const viewer = new Cesium.Viewer(containerRef.current, {
      baseLayer: new Cesium.ImageryLayer(
        new Cesium.OpenStreetMapImageryProvider({
          url: 'https://tile.openstreetmap.org/'
        })
      ),
      terrainProvider: new Cesium.EllipsoidTerrainProvider(),
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      selectionIndicator: true,
      infoBox: false,
    });

    viewerRef.current = viewer;

    // Explicitly enable mouse screen space camera controller & restore scroll-wheel zoom
    const controller = viewer.scene.screenSpaceCameraController;
    controller.enableInputs = true;
    controller.enableZoom = true;
    controller.enableRotate = true;
    controller.enableTilt = true;
    controller.enableTranslate = true;
    controller.enableLook = true;

    // Restore mouse wheel, pinch, and drag zoom event types
    controller.zoomEventTypes = [
      Cesium.CameraEventType.WHEEL,
      Cesium.CameraEventType.PINCH,
      Cesium.CameraEventType.RIGHT_DRAG,
      {
        eventType: Cesium.CameraEventType.WHEEL,
        modifier: Cesium.KeyboardEventModifier.CTRL
      }
    ];

    // Ensure camera min and max zoom distances allow full range zooming
    controller.minimumZoomDistance = 1.0;
    controller.maximumZoomDistance = 50000000.0;

    // Ensure canvas is focusable for mouse wheel input events
    if (viewer.scene.canvas) {
      viewer.scene.canvas.setAttribute('tabindex', '0');
    }

    // Force viewer.resize() immediately after creation as safety net
    viewer.resize();

    // Additional resize calls for layout transitions & paint delays
    requestAnimationFrame(() => {
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.resize();
      }
    });

    const resizeTimeout = setTimeout(() => {
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.resize();
      }
    }, 150);

    // Window resize event listener
    const handleResize = () => {
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.resize();
      }
    };
    window.addEventListener('resize', handleResize);

    // ResizeObserver to monitor container element dimension changes
    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined' && containerRef.current) {
      resizeObserver = new ResizeObserver(() => {
        if (viewerRef.current && !viewerRef.current.isDestroyed()) {
          viewerRef.current.resize();
        }
      });
      resizeObserver.observe(containerRef.current);
    }

    // Center camera on Indian Ocean (78°E, 12°N)
    viewer.camera.setView({
      destination: DEFAULT_CAMERA_DESTINATION,
      orientation: {
        heading: Cesium.Math.toRadians(0.0),
        pitch: Cesium.Math.toRadians(-80.0),
        roll: 0.0
      }
    });

    // Add click handler for float selection
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    handler.setInputAction((click: any) => {
      const pickedObject = viewer.scene.pick(click.position);
      if (Cesium.defined(pickedObject) && pickedObject.id && pickedObject.id.properties) {
        const props = pickedObject.id.properties;
        if (props.floatData) {
          const floatObj = props.floatData.getValue();
          onSelectFloat(floatObj);

          // Fly camera smoothly to float position
          viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(floatObj.longitude, floatObj.latitude, 350000.0),
            duration: 1.5
          });
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      clearTimeout(resizeTimeout);
      handler.destroy();
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy();
        viewerRef.current = null;
      }
    };
  }, []);

  // Update Float Markers on Globe (Requirement #1 & #4)
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    // Confirm floats count reaching component
    console.log('GlobeView floats count:', floats.length);

    // Remove existing float entities
    const floatEntities = viewer.entities.values.filter(e => e.name === 'floatEntity');
    floatEntities.forEach(e => viewer.entities.remove(e));

    // Single loop over floats array for both normal & anomaly floats
    floats.forEach(f => {
      const isAnomaly = f.has_anomaly;
      
      if (isAnomaly) {
        // Requirement #4: Flickering warning bulb effect with jitter (150ms-300ms)
        let lastToggle = Date.now();
        let isLit = true;
        let nextInterval = 200;

        const colorCallback = new Cesium.CallbackProperty(() => {
          const now = Date.now();
          if (now - lastToggle > nextInterval) {
            isLit = !isLit;
            lastToggle = now;
            nextInterval = 150 + Math.random() * 150; // 150-300ms with jitter
          }
          return isLit 
            ? Cesium.Color.fromCssColorString('#FF3B30') 
            : Cesium.Color.fromCssColorString('#FF3B30').withAlpha(0.35);
        }, false);

        const sizeCallback = new Cesium.CallbackProperty(() => {
          return isLit ? 18 : 12;
        }, false);

        const outlineWidthCallback = new Cesium.CallbackProperty(() => {
          return isLit ? 4 : 2;
        }, false);

        const ringAlphaCallback = new Cesium.CallbackProperty(() => {
          return isLit ? 0.35 : 0.12;
        }, false);

        // Core flickering point entity
        viewer.entities.add({
          name: 'floatEntity',
          position: Cesium.Cartesian3.fromDegrees(f.longitude, f.latitude, 100.0),
          point: {
            pixelSize: sizeCallback as any,
            color: colorCallback as any,
            outlineColor: Cesium.Color.fromCssColorString('#FFD700'),
            outlineWidth: outlineWidthCallback as any,
            scaleByDistance: new Cesium.NearFarScalar(1.0e2, 1.5, 1.5e7, 1.2), // Zoom-out visibility
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          label: {
            text: `⚠️ ${f.float_id}`,
            font: 'bold 11px sans-serif',
            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            fillColor: Cesium.Color.fromCssColorString('#FF3B30'),
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2,
            pixelOffset: new Cesium.Cartesian2(0, -20),
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          properties: new Cesium.PropertyBag({ floatData: f })
        });

        // Soft outer glowing ring synchronized with flicker
        viewer.entities.add({
          name: 'floatEntity',
          position: Cesium.Cartesian3.fromDegrees(f.longitude, f.latitude, 0.0),
          ellipse: {
            semiMinorAxis: 130000.0,
            semiMajorAxis: 130000.0,
            material: new Cesium.ColorMaterialProperty(
              new Cesium.CallbackProperty(() => Cesium.Color.fromCssColorString('#FF3B30').withAlpha(isLit ? 0.35 : 0.1), false) as any
            ),
            outline: true,
            outlineColor: Cesium.Color.fromCssColorString('#FF3B30'),
            outlineWidth: 2
          }
        });
      } else {
        // Requirement #1: Normal Float -> Static Navy Blue Marker (#0284C7)
        viewer.entities.add({
          name: 'floatEntity',
          position: Cesium.Cartesian3.fromDegrees(f.longitude, f.latitude, 100.0),
          point: {
            pixelSize: 10,
            color: Cesium.Color.fromCssColorString('#0284C7'), // Navy Blue
            outlineColor: Cesium.Color.WHITE,
            outlineWidth: 1.5,
            scaleByDistance: new Cesium.NearFarScalar(1.0e2, 1.2, 1.5e7, 1.0),
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          label: {
            text: f.float_id,
            font: '10px sans-serif',
            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            fillColor: Cesium.Color.WHITE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2,
            pixelOffset: new Cesium.Cartesian2(0, -16),
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          properties: new Cesium.PropertyBag({ floatData: f })
        });
      }
    });
  }, [floats, variable]);

  // Requirement #2: Render Ocean Glider Polyline Trajectories
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    const gliderEntities = viewer.entities.values.filter(e => e.name === 'gliderEntity');
    gliderEntities.forEach(e => viewer.entities.remove(e));

    if (!showGliders) return;

    gliders.forEach(g => {
      // Flatten positions array into valid Cartesian3 points
      const positions = (g.path || [])
        .filter(pt => pt && pt.lon !== undefined && pt.lat !== undefined)
        .map(pt => Cesium.Cartesian3.fromDegrees(pt.lon, pt.lat, 100.0));
      
      if (positions.length >= 2) {
        // Polyline trajectory path
        viewer.entities.add({
          name: 'gliderEntity',
          polyline: {
            positions: positions,
            width: 3.5,
            material: new Cesium.PolylineGlowMaterialProperty({
              glowPower: 0.25,
              color: Cesium.Color.fromCssColorString('#00F0FF')
            })
          }
        });
      }

      // Glider current position marker
      viewer.entities.add({
        name: 'gliderEntity',
        position: Cesium.Cartesian3.fromDegrees(g.current_lon, g.current_lat, 200.0),
        point: {
          pixelSize: 12,
          color: Cesium.Color.YELLOW,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 2,
          disableDepthTestDistance: Number.POSITIVE_INFINITY
        },
        label: {
          text: `🛸 ${g.name}`,
          font: 'bold 10px sans-serif',
          fillColor: Cesium.Color.YELLOW,
          pixelOffset: new Cesium.Cartesian2(0, 18),
          disableDepthTestDistance: Number.POSITIVE_INFINITY
        }
      });
    });
  }, [gliders, showGliders]);

  // Requirement: Heatmap Surface Layer Overlay Rendering
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    // Console-log dataset length right before rendering (debug requirement #4)
    console.log('Heatmap dataset length:', gridPoints.length);

    // Remove existing heatmap entities
    const heatmapEntities = viewer.entities.values.filter(e => e.name === 'heatmapEntity');
    heatmapEntities.forEach(e => viewer.entities.remove(e));

    if (!showHeatmap || gridPoints.length === 0) return;

    const step = 2.5; // 5-degree grid step (±2.5°)
    gridPoints.forEach(pt => {
      const colorHex = getHeatmapColor(variable, pt.value);
      viewer.entities.add({
        name: 'heatmapEntity',
        rectangle: {
          coordinates: Cesium.Rectangle.fromDegrees(
            pt.lon - step,
            pt.lat - step,
            pt.lon + step,
            pt.lat + step
          ),
          material: Cesium.Color.fromCssColorString(colorHex).withAlpha(0.55),
          height: 0.0
        }
      });
    });
  }, [gridPoints, showHeatmap, variable]);

  // Handle Fly-To on float selection from list or deselection
  const prevSelectedRef = useRef<FloatProfile | null>(null);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    if (selectedFloat) {
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(selectedFloat.longitude, selectedFloat.latitude, 350000.0),
        duration: 1.2
      });
    } else if (prevSelectedRef.current !== null && !selectedFloat) {
      // Float was closed / deselected -> fly back to full globe
      console.log('Float deselected, flying camera back to full globe');
      const targetDestination = Cesium.Cartesian3.fromDegrees(78.0, 12.0, 6500000.0);
      viewer.camera.flyTo({
        destination: targetDestination,
        orientation: {
          heading: Cesium.Math.toRadians(0.0),
          pitch: Cesium.Math.toRadians(-80.0),
          roll: 0.0
        },
        duration: 1.5
      });
    }
    prevSelectedRef.current = selectedFloat;
  }, [selectedFloat]);

  const [mapStyle, setMapStyle] = useState<'standard' | 'satellite' | 'dark'>('standard');

  const handleStyleChange = async (style: 'standard' | 'satellite' | 'dark') => {
    setMapStyle(style);
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    viewer.imageryLayers.removeAll();

    if (style === 'satellite') {
      // High-Resolution Free ArcGIS World Imagery
      try {
        const provider = (Cesium as any).ArcGisMapServerImageryProvider.fromUrl 
          ? await (Cesium as any).ArcGisMapServerImageryProvider.fromUrl('https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer')
          : new (Cesium as any).ArcGisMapServerImageryProvider({ url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer' });
        viewer.imageryLayers.addImageryProvider(provider);
      } catch (err) {
        viewer.imageryLayers.addImageryProvider(new Cesium.OpenStreetMapImageryProvider({ url: 'https://tile.openstreetmap.org/' }));
      }
    } else if (style === 'dark') {
      // Free CartoDB Dark Matter Basemap
      viewer.imageryLayers.addImageryProvider(
        new Cesium.UrlTemplateImageryProvider({
          url: 'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'
        })
      );
    } else {
      // Standard OpenStreetMap (Guaranteed Default)
      viewer.imageryLayers.addImageryProvider(
        new Cesium.OpenStreetMapImageryProvider({
          url: 'https://tile.openstreetmap.org/'
        })
      );
    }
  };

  return (
    <div className="absolute inset-0 w-full h-full overflow-hidden">
      {/* Cesium Canvas Container */}
      <div
        ref={containerRef}
        tabIndex={0}
        className="absolute inset-0 w-full h-full bg-ocean-dark focus:outline-none"
        style={{ width: '100%', height: '100%' }}
      />

      {/* Reset View Button */}
      <div className="absolute top-20 left-6 z-20">
        <button
          onClick={handleResetCamera}
          className="flex items-center space-x-2 px-3 py-2 rounded-xl glass-panel border border-cyan-500/40 text-cyan-300 hover:text-white hover:bg-cyan-950/60 cursor-pointer shadow-glass transition-all active:scale-95 text-xs font-semibold"
          title="Reset Camera View to Full Indian Ocean Globe"
        >
          <RotateCcw className="w-4 h-4" />
          <span>Reset Globe View</span>
        </button>
      </div>

      {/* Imagery Style Selector (Standard / Satellite / Dark Ocean) */}
      <div className="absolute top-20 right-6 z-20 flex items-center space-x-1 p-1 rounded-xl glass-panel border border-slate-700/80 shadow-glass">
        <button
          onClick={() => handleStyleChange('standard')}
          className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-all ${
            mapStyle === 'standard' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          🗺️ Standard
        </button>
        <button
          onClick={() => handleStyleChange('satellite')}
          className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-all ${
            mapStyle === 'satellite' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          🛰️ Satellite
        </button>
        <button
          onClick={() => handleStyleChange('dark')}
          className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-all ${
            mapStyle === 'dark' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          🌌 Dark Ocean
        </button>
      </div>

      {/* Requirement: Empty State Display when filters yield no floats */}
      {floats.length === 0 && (
        <div className="absolute inset-0 z-20 flex items-center justify-center pointer-events-none p-4">
          <div className="glass-panel rounded-2xl p-6 border border-amber-500/50 shadow-glass text-center max-w-md pointer-events-auto space-y-3 animate-in zoom-in-95 duration-200">
            <div className="w-12 h-12 rounded-full bg-amber-950/80 border border-amber-500/50 flex items-center justify-center mx-auto text-amber-400">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h3 className="text-base font-bold text-white">No Observation Data For This Selection</h3>
            <p className="text-xs text-slate-300">
              No Argo floats match depth level <span className="text-amber-300 font-mono">{maxDepth}m</span> in this sub-region.
              Try adjusting the depth slider or selecting "All Regions".
            </p>
          </div>
        </div>
      )}

      {/* Map Legend Overlay */}
      <div className="absolute bottom-6 left-6 z-20 glass-panel rounded-xl p-3 border border-slate-700/70 text-[11px] space-y-1.5 shadow-glass">
        <div className="font-semibold text-slate-200 flex items-center space-x-1">
          <Compass className="w-3.5 h-3.5 text-cyan-400" />
          <span>3D Map Legend</span>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-slate-300 text-[10px]">
          <span className="flex items-center"><span className="w-2.5 h-2.5 rounded-full bg-sky-500 mr-1.5"></span> Normal Float</span>
          <span className="flex items-center"><span className="w-2.5 h-2.5 rounded-full bg-red-500 mr-1.5 animate-pulse"></span> Anomaly Warning</span>
          <span className="flex items-center"><span className="w-2.5 h-2.5 rounded-full bg-yellow-400 mr-1.5"></span> Ocean Glider</span>
          <span className="flex items-center"><span className="w-4 h-0.5 bg-cyan-400 mr-1.5"></span> Glider Track</span>
        </div>

        {showHeatmap && (
          <div className="pt-1.5 border-t border-slate-700/60 space-y-1">
            <div className="flex justify-between text-[9px] font-mono text-cyan-300">
              <span className="capitalize">🌊 {variable} Grid Heatmap</span>
              <span>{variable === 'temperature' ? '15°C – 30°C' : variable === 'salinity' ? '32 – 37 PSU' : '0.0 – 1.2 mg/m³'}</span>
            </div>
            <div
              className="h-2 w-full rounded-full border border-slate-700"
              style={{
                background: variable === 'temperature'
                  ? 'linear-gradient(to right, #1d4ed8, #0284c7, #06b6d4, #eab308, #f97316, #ef4444)'
                  : variable === 'salinity'
                  ? 'linear-gradient(to right, #10b981, #06b6d4, #3b82f6, #8b5cf6, #d946ef)'
                  : 'linear-gradient(to right, #0369a1, #14b8a6, #22c55e, #84cc16, #10b981)'
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
};

