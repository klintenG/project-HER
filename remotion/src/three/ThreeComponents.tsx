/**
 * Project HER v2.0 – 3D Scene Components
 * ========================================
 * Three.js components for @remotion/three integration.
 *
 * Provides:
 * - ThreeDText: Animated 3D text with extrusion
 * - ThreeDCamera: Cinematic camera movements
 * - ParticleField: Ambient 3D particles
 * - FloatingShapes: Random 3D shapes background
 * - ThreeDScene: Top-level wrapper for any 3D content
 */

import React, { useRef, useMemo } from "react";
import { useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { Text3D, Center, Float, MeshDistortMaterial } from "@react-three/drei";

// ═══════════════════════════════════════════════════
//  ANIMATED CAMERA
// ═══════════════════════════════════════════════════

interface AnimatedCameraProps {
  animation?: "orbit" | "push_in" | "pull_out" | "pan_left" | "pan_right" | "crane_up" | "static";
  intensity?: number;
}

export const AnimatedCamera: React.FC<AnimatedCameraProps> = ({
  animation = "static",
  intensity = 1,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const { camera } = useThree();
  const progress = frame / durationInFrames;

  useFrame(() => {
    const cam = camera as THREE.PerspectiveCamera;
    const i = intensity;

    switch (animation) {
      case "orbit": {
        const angle = progress * Math.PI * 2 * 0.3 * i;
        cam.position.x = Math.sin(angle) * 5;
        cam.position.z = Math.cos(angle) * 5;
        cam.lookAt(0, 0, 0);
        break;
      }
      case "push_in": {
        const z = interpolate(progress, [0, 1], [8, 3]) * i;
        cam.position.z = z;
        cam.lookAt(0, 0, 0);
        break;
      }
      case "pull_out": {
        const z = interpolate(progress, [0, 1], [3, 8]) * i;
        cam.position.z = z;
        cam.lookAt(0, 0, 0);
        break;
      }
      case "pan_left": {
        const x = interpolate(progress, [0, 1], [2, -2]) * i;
        cam.position.x = x;
        cam.lookAt(0, 0, 0);
        break;
      }
      case "pan_right": {
        const x = interpolate(progress, [0, 1], [-2, 2]) * i;
        cam.position.x = x;
        cam.lookAt(0, 0, 0);
        break;
      }
      case "crane_up": {
        const y = interpolate(progress, [0, 1], [-1, 3]) * i;
        cam.position.y = y;
        cam.lookAt(0, 0, 0);
        break;
      }
      case "static":
      default:
        cam.position.set(0, 0, 5);
        cam.lookAt(0, 0, 0);
        break;
    }
  });

  return null;
};

// ═══════════════════════════════════════════════════
//  PARTICLE FIELD
// ═══════════════════════════════════════════════════

interface ParticleFieldProps {
  count?: number;
  color?: string;
  speed?: number;
  size?: number;
  spread?: number;
}

export const ParticleField: React.FC<ParticleFieldProps> = ({
  count = 200,
  color = "#ffffff",
  speed = 0.5,
  size = 0.03,
  spread = 10,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ref = useRef<THREE.Points>(null);
  const t = (frame / fps) * speed;

  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * spread;
      arr[i * 3 + 1] = (Math.random() - 0.5) * spread;
      arr[i * 3 + 2] = (Math.random() - 0.5) * spread;
    }
    return arr;
  }, [count, spread]);

  useFrame(() => {
    if (!ref.current) return;
    const pos = ref.current.geometry.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < count; i++) {
      const y = positions[i * 3 + 1] + t * 0.3;
      pos.setY(i, ((y % spread) + spread) % spread - spread / 2);
    }
    pos.needsUpdate = true;
    ref.current.rotation.y = t * 0.1;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        color={color}
        size={size}
        transparent
        opacity={0.8}
        sizeAttenuation
      />
    </points>
  );
};

// ═══════════════════════════════════════════════════
//  FLOATING SHAPES
// ═══════════════════════════════════════════════════

interface FloatingShapesProps {
  count?: number;
  colors?: string[];
  shapeTypes?: ("sphere" | "box" | "torus" | "octahedron" | "cone")[];
}

const ShapeGeometry: React.FC<{ type: string }> = ({ type }) => {
  switch (type) {
    case "sphere":
      return <sphereGeometry args={[0.3, 16, 16]} />;
    case "box":
      return <boxGeometry args={[0.4, 0.4, 0.4]} />;
    case "torus":
      return <torusGeometry args={[0.25, 0.1, 8, 16]} />;
    case "octahedron":
      return <octahedronGeometry args={[0.3]} />;
    case "cone":
      return <coneGeometry args={[0.25, 0.5, 8]} />;
    default:
      return <sphereGeometry args={[0.3, 16, 16]} />;
  }
};

export const FloatingShapes: React.FC<FloatingShapesProps> = ({
  count = 8,
  colors = ["#FF6B8A", "#6B8AFF", "#8AFF6B", "#FFD700", "#FF6BFF"],
  shapeTypes = ["sphere", "box", "torus", "octahedron"],
}) => {
  const shapes = useMemo(() => {
    return Array.from({ length: count }, (_, i) => ({
      position: [
        (Math.random() - 0.5) * 6,
        (Math.random() - 0.5) * 8,
        (Math.random() - 0.5) * 4,
      ] as [number, number, number],
      rotation: [Math.random() * Math.PI, Math.random() * Math.PI, 0] as [number, number, number],
      color: colors[i % colors.length],
      type: shapeTypes[i % shapeTypes.length],
      speed: 0.5 + Math.random() * 1.5,
      floatIntensity: 0.5 + Math.random() * 2,
    }));
  }, [count, colors, shapeTypes]);

  return (
    <>
      {shapes.map((s, i) => (
        <Float
          key={i}
          speed={s.speed}
          floatIntensity={s.floatIntensity}
          rotationIntensity={0.5}
        >
          <mesh position={s.position} rotation={s.rotation}>
            <ShapeGeometry type={s.type} />
            <MeshDistortMaterial
              color={s.color}
              speed={2}
              distort={0.15}
              roughness={0.4}
              metalness={0.3}
            />
          </mesh>
        </Float>
      ))}
    </>
  );
};

// ═══════════════════════════════════════════════════
//  3D TEXT (Title rendering)
// ═══════════════════════════════════════════════════

interface ThreeDTextProps {
  text: string;
  color?: string;
  size?: number;
  depth?: number;
  animation?: "float" | "rotate" | "pulse" | "typewriter" | "static";
  fontUrl?: string;
}

export const ThreeDTextBlock: React.FC<ThreeDTextProps> = ({
  text,
  color = "#ffffff",
  size = 0.5,
  depth = 0.2,
  animation = "float",
  fontUrl = "/fonts/Inter_Bold.json",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const ref = useRef<THREE.Group>(null);
  const progress = frame / durationInFrames;

  const entrySpring = spring({ frame, fps, config: { damping: 15, mass: 0.8 } });

  useFrame(() => {
    if (!ref.current) return;
    const t = frame / fps;

    switch (animation) {
      case "float":
        ref.current.position.y = Math.sin(t * 2) * 0.1;
        ref.current.rotation.y = Math.sin(t * 0.5) * 0.05;
        break;
      case "rotate":
        ref.current.rotation.y = progress * Math.PI * 2;
        break;
      case "pulse": {
        const s = 1 + Math.sin(t * 3) * 0.05;
        ref.current.scale.set(s, s, s);
        break;
      }
      case "typewriter":
        // Handled via visibleChars below
        break;
    }
  });

  return (
    <group ref={ref} scale={entrySpring}>
      <Center>
        <Text3D
          font={fontUrl}
          size={size}
          height={depth}
          bevelEnabled
          bevelSize={0.02}
          bevelThickness={0.01}
        >
          {animation === "typewriter"
            ? text.slice(0, Math.floor(progress * text.length * 1.2))
            : text}
          <meshStandardMaterial color={color} metalness={0.5} roughness={0.3} />
        </Text3D>
      </Center>
    </group>
  );
};

// ═══════════════════════════════════════════════════
//  ENVIRONMENT LIGHTING
// ═══════════════════════════════════════════════════

interface EnvironmentLightingProps {
  mood?: "warm" | "cool" | "dramatic" | "neutral" | "neon";
}

export const EnvironmentLighting: React.FC<EnvironmentLightingProps> = ({
  mood = "neutral",
}) => {
  const configs: Record<string, { ambient: string; dir: string; intensity: number }> = {
    warm: { ambient: "#FFE4B5", dir: "#FF8C00", intensity: 1.5 },
    cool: { ambient: "#B0C4DE", dir: "#4682B4", intensity: 1.2 },
    dramatic: { ambient: "#2D1B4E", dir: "#FF4500", intensity: 2.0 },
    neutral: { ambient: "#F5F5F5", dir: "#FFFFFF", intensity: 1.0 },
    neon: { ambient: "#0D0221", dir: "#FF00FF", intensity: 1.8 },
  };

  const c = configs[mood] || configs.neutral;

  return (
    <>
      <ambientLight color={c.ambient} intensity={0.4} />
      <directionalLight
        color={c.dir}
        intensity={c.intensity}
        position={[5, 5, 5]}
        castShadow
      />
      <pointLight
        color={c.dir}
        intensity={c.intensity * 0.5}
        position={[-3, -2, 4]}
      />
    </>
  );
};

// ═══════════════════════════════════════════════════
//  ANIMATED PLANE (for background texture/image)
// ═══════════════════════════════════════════════════

interface AnimatedPlaneProps {
  textureUrl?: string;
  color?: string;
  animation?: "wave" | "breathing" | "static";
}

export const AnimatedPlane: React.FC<AnimatedPlaneProps> = ({
  textureUrl,
  color = "#1a1a2e",
  animation = "static",
}) => {
  const ref = useRef<THREE.Mesh>(null);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const texture = useMemo(() => {
    if (!textureUrl) return null;
    const loader = new THREE.TextureLoader();
    return loader.load(textureUrl);
  }, [textureUrl]);

  useFrame(() => {
    if (!ref.current) return;
    const mat = ref.current.material as THREE.MeshStandardMaterial;

    if (animation === "breathing") {
      const s = 1 + Math.sin(t * 1.5) * 0.02;
      ref.current.scale.set(s, s, 1);
    } else if (animation === "wave") {
      ref.current.rotation.z = Math.sin(t * 0.5) * 0.02;
    }
  });

  return (
    <mesh ref={ref} position={[0, 0, -2]}>
      <planeGeometry args={[12, 20]} />
      <meshStandardMaterial
        color={texture ? undefined : color}
        map={texture || undefined}
        transparent
        opacity={0.9}
      />
    </mesh>
  );
};

// ═══════════════════════════════════════════════════
//  TOP-LEVEL 3D SCENE WRAPPER
// ═══════════════════════════════════════════════════

interface ThreeDSceneProps {
  children: React.ReactNode;
  camera?: AnimatedCameraProps;
  lighting?: EnvironmentLightingProps["mood"];
  background?: string;
  width: number;
  height: number;
}

export const ThreeDScene: React.FC<ThreeDSceneProps> = ({
  children,
  camera = {},
  lighting = "neutral",
  background = "#0D0D0D",
  width,
  height,
}) => {
  return (
    <ThreeCanvas
      width={width}
      height={height}
      style={{ position: "absolute", top: 0, left: 0 }}
      orthographic={false}
      camera={{ position: [0, 0, 5], fov: 50 }}
    >
      <color attach="background" args={[background]} />
      <EnvironmentLighting mood={lighting} />
      <AnimatedCamera {...camera} />
      <fog attach="fog" args={[background, 8, 20]} />
      {children}
    </ThreeCanvas>
  );
};
