'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import * as d3 from 'd3'

interface Gate {
  type: string
  qubit: number
  control?: number
  target?: number
  angle?: number
  name?: string
  qubits?: number[]
  timestamp?: number
}

interface CircuitVisualizationProps {
  gates: Gate[]
  qubits: number
  className?: string
}

export default function CircuitVisualization({ gates, qubits, className = '' }: CircuitVisualizationProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [selectedGate, setSelectedGate] = useState<Gate | null>(null)
  const [hoveredGate, setHoveredGate] = useState<Gate | null>(null)
  const [isDarkMode, setIsDarkMode] = useState(true)

  // Detect theme
  useEffect(() => {
    const checkTheme = () => {
      setIsDarkMode(!document.documentElement.classList.contains('light'))
    }
    checkTheme()
    const observer = new MutationObserver(checkTheme)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])

  // Theme colors. Memoised: a fresh object every render made the d3 effect
  // below (which lists `colors` as a dependency) redraw the whole SVG on every
  // parent re-render, i.e. on every debounced keystroke in the editor.
  const colors = useMemo(() => ({
    background: isDarkMode ? '#1e1e1e' : '#ffffff',
    qubitLine: isDarkMode ? '#4B5563' : '#9CA3AF',
    qubitLabel: isDarkMode ? '#9CA3AF' : '#6B7280',
    gateStroke: isDarkMode ? '#6B7280' : '#4B5563',
    text: isDarkMode ? '#ffffff' : '#1F2937',
    hover: isDarkMode ? '#3B82F6' : '#2563EB',
    selected: isDarkMode ? '#10B981' : '#059669',
  }), [isDarkMode])

  useEffect(() => {
    if (!svgRef.current || gates.length === 0) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const margin = { top: 20, right: 20, bottom: 20, left: 60 }
    const qubitSpacing = 60
    const gateSpacing = 80
    
    // Calculate max timestamp for width calculation
    const maxTimestamp = gates.reduce((max, gate) => {
      const ts = gate.timestamp ?? 0
      return Math.max(max, ts)
    }, 0)
    
    // Calculate width based on timestamps (circuit depth), ensuring minimum width
    const minWidth = 600
    const circuitDepth = maxTimestamp + 1
    const calculatedWidth = Math.max(minWidth, circuitDepth * gateSpacing + margin.left + margin.right)
    const width = calculatedWidth
    const height = qubits * qubitSpacing + margin.top + margin.bottom

    svg.attr('width', width).attr('height', height)

    // Create main group with zoom transform
    const mainGroup = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

    // Setup zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 3])
      .on('zoom', (event) => {
        mainGroup.attr('transform', `translate(${margin.left + event.transform.x},${margin.top + event.transform.y}) scale(${event.transform.k})`)
      })

    svg.call(zoom as any)

    // Draw qubit lines
    for (let i = 0; i < qubits; i++) {
      const y = i * qubitSpacing + 30
      
      mainGroup.append('line')
        .attr('x1', 0)
        .attr('y1', y)
        .attr('x2', width - margin.left - margin.right)
        .attr('y2', y)
        .attr('stroke', colors.qubitLine)
        .attr('stroke-width', 2)
        .attr('class', 'qubit-line')

      mainGroup.append('text')
        .attr('x', -10)
        .attr('y', y + 5)
        .attr('text-anchor', 'end')
        .attr('fill', colors.qubitLabel)
        .attr('font-family', 'monospace')
        .attr('font-size', '14px')
        .attr('class', 'qubit-label')
        .text(`q${i}`)
    }

    // Gate color helper
    const getGateColor = (gateType: string, property: 'fill' | 'stroke'): string => {
      const type = gateType.toLowerCase()
      const gateColors: Record<string, { fill: string; stroke: string }> = {
        h: { fill: '#3B82F6', stroke: '#1D4ED8' },
        x: { fill: '#EF4444', stroke: '#DC2626' },
        y: { fill: '#10B981', stroke: '#059669' },
        z: { fill: '#8B5CF6', stroke: '#7C3AED' },
        s: { fill: '#06B6D4', stroke: '#0891B2' },
        t: { fill: '#14B8A6', stroke: '#0D9488' },
        rx: { fill: '#F59E0B', stroke: '#D97706' },
        ry: { fill: '#F59E0B', stroke: '#D97706' },
        rz: { fill: '#F59E0B', stroke: '#D97706' },
        p: { fill: '#F59E0B', stroke: '#D97706' },
        measure: { fill: '#6B7280', stroke: '#4B5563' },
      }
      return gateColors[type]?.[property] || (isDarkMode ? '#6B7280' : '#9CA3AF')
    }

    // Get gate info for tooltip
    const getGateInfo = (gate: Gate): string => {
      let info = `<strong>${gate.type.toUpperCase()}</strong><br/>`
      if (gate.control !== undefined && gate.target !== undefined) {
        info += `Control: q${gate.control}<br/>Target: q${gate.target}`
      } else {
        info += `Qubit: q${gate.qubit}`
      }
      if (gate.angle !== undefined) {
        info += `<br/>Angle: ${gate.angle.toFixed(3)} rad`
        info += `<br/>Angle: ${(gate.angle * 180 / Math.PI).toFixed(1)}°`
      }
      return info
    }

    // Create tooltip
    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'circuit-tooltip')
      .style('opacity', 0)
      .style('position', 'absolute')
      .style('background', isDarkMode ? '#1F2937' : '#F3F4F6')
      .style('color', colors.text)
      .style('padding', '8px 12px')
      .style('border-radius', '6px')
      .style('font-size', '12px')
      .style('font-family', 'monospace')
      .style('pointer-events', 'none')
      .style('z-index', '1000')
      .style('box-shadow', '0 4px 6px rgba(0,0,0,0.1)')
      .style('border', `1px solid ${colors.gateStroke}`)

    // Drawing functions - defined inside useEffect to access getGateColor and colors
    function drawHGate(g: d3.Selection<SVGGElement, unknown, null, undefined>, x: number, y: number, label: string, gate: Gate) {
      g.attr('data-gate-type', 'h')
      g.append('rect')
        .attr('x', x - 15)
        .attr('y', y - 15)
        .attr('width', 30)
        .attr('height', 30)
        .attr('fill', getGateColor('h', 'fill'))
        .attr('stroke', getGateColor('h', 'stroke'))
        .attr('stroke-width', 2)
        .attr('rx', 4)
        .attr('class', 'gate-element')
      g.append('text')
        .attr('x', x)
        .attr('y', y + 5)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-family', 'monospace')
        .attr('font-size', '14px')
        .attr('font-weight', 'bold')
        .text(label)
    }

    function drawXGate(g: d3.Selection<SVGGElement, unknown, null, undefined>, x: number, y: number, gate: Gate) {
      g.attr('data-gate-type', 'x')
      g.append('circle')
        .attr('cx', x)
        .attr('cy', y)
        .attr('r', 15)
        .attr('fill', getGateColor('x', 'fill'))
        .attr('stroke', getGateColor('x', 'stroke'))
        .attr('stroke-width', 2)
        .attr('class', 'gate-element')
      g.append('text')
        .attr('x', x)
        .attr('y', y + 5)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-family', 'monospace')
        .attr('font-size', '14px')
        .attr('font-weight', 'bold')
        .text('X')
    }

    function drawYGate(g: d3.Selection<SVGGElement, unknown, null, undefined>, x: number, y: number, gate: Gate) {
      g.attr('data-gate-type', 'y')
      g.append('circle')
        .attr('cx', x)
        .attr('cy', y)
        .attr('r', 15)
        .attr('fill', getGateColor('y', 'fill'))
        .attr('stroke', getGateColor('y', 'stroke'))
        .attr('stroke-width', 2)
        .attr('class', 'gate-element')
      g.append('text')
        .attr('x', x)
        .attr('y', y + 5)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-family', 'monospace')
        .attr('font-size', '14px')
        .attr('font-weight', 'bold')
        .text('Y')
    }

    function drawZGate(g: d3.Selection<SVGGElement, unknown, null, undefined>, x: number, y: number, gate: Gate) {
      g.attr('data-gate-type', 'z')
      g.append('circle')
        .attr('cx', x)
        .attr('cy', y)
        .attr('r', 15)
        .attr('fill', getGateColor('z', 'fill'))
        .attr('stroke', getGateColor('z', 'stroke'))
        .attr('stroke-width', 2)
        .attr('class', 'gate-element')
      g.append('text')
        .attr('x', x)
        .attr('y', y + 5)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-family', 'monospace')
        .attr('font-size', '14px')
        .attr('font-weight', 'bold')
        .text('Z')
    }

    function drawSGate(g: d3.Selection<SVGGElement, unknown, null, undefined>, x: number, y: number, gate: Gate) {
      g.attr('data-gate-type', 's')
      g.append('rect')
        .attr('x', x - 15)
        .attr('y', y - 15)
        .attr('width', 30)
        .attr('height', 30)
        .attr('fill', getGateColor('s', 'fill'))
        .attr('stroke', getGateColor('s', 'stroke'))
        .attr('stroke-width', 2)
        .attr('rx', 4)
        .attr('class', 'gate-element')
      g.append('text')
        .attr('x', x)
        .attr('y', y + 5)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-family', 'monospace')
        .attr('font-size', '14px')
        .attr('font-weight', 'bold')
        .text('S')
    }

    function drawTGate(g: d3.Selection<SVGGElement, unknown, null, undefined>, x: number, y: number, gate: Gate) {
      g.attr('data-gate-type', 't')
      g.append('rect')
        .attr('x', x - 15)
        .attr('y', y - 15)
        .attr('width', 30)
        .attr('height', 30)
        .attr('fill', getGateColor('t', 'fill'))
        .attr('stroke', getGateColor('t', 'stroke'))
        .attr('stroke-width', 2)
        .attr('rx', 4)
        .attr('class', 'gate-element')
      g.append('text')
        .attr('x', x)
        .attr('y', y + 5)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-family', 'monospace')
        .attr('font-size', '14px')
        .attr('font-weight', 'bold')
        .text('T')
    }

    function drawCNOTGate(g: d3.Selection<SVGGElement, unknown, null, undefined>, x: number, controlY: number, targetY: number, gate: Gate) {
      g.attr('data-gate-type', 'cx')
      g.append('circle')
        .attr('cx', x)
        .attr('cy', controlY)
        .attr('r', 6)
        .attr('fill', colors.background)
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
        .attr('class', 'gate-element')
      g.append('line')
        .attr('x1', x)
        .attr('y1', controlY)
        .attr('x2', x)
        .attr('y2', targetY)
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
      g.append('circle')
        .attr('cx', x)
        .attr('cy', targetY)
        .attr('r', 15)
        .attr('fill', 'none')
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
        .attr('class', 'gate-element')
      g.append('line')
        .attr('x1', x - 8)
        .attr('y1', targetY - 8)
        .attr('x2', x + 8)
        .attr('y2', targetY + 8)
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
      g.append('line')
        .attr('x1', x - 8)
        .attr('y1', targetY + 8)
        .attr('x2', x + 8)
        .attr('y2', targetY - 8)
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
    }

    function drawCZGate(g: d3.Selection<SVGGElement, unknown, null, undefined>, x: number, controlY: number, targetY: number, gate: Gate) {
      g.attr('data-gate-type', 'cz')
      g.append('circle')
        .attr('cx', x)
        .attr('cy', controlY)
        .attr('r', 6)
        .attr('fill', colors.background)
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
        .attr('class', 'gate-element')
      g.append('line')
        .attr('x1', x)
        .attr('y1', controlY)
        .attr('x2', x)
        .attr('y2', targetY)
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
      g.append('circle')
        .attr('cx', x)
        .attr('cy', targetY)
        .attr('r', 6)
        .attr('fill', colors.background)
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
        .attr('class', 'gate-element')
    }

    function drawSWAPGate(g: d3.Selection<SVGGElement, unknown, null, undefined>, x: number, qubit1Y: number, qubit2Y: number, gate: Gate) {
      g.attr('data-gate-type', 'swap')
      g.append('line')
        .attr('x1', x - 8)
        .attr('y1', qubit1Y - 8)
        .attr('x2', x + 8)
        .attr('y2', qubit1Y + 8)
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
      g.append('line')
        .attr('x1', x - 8)
        .attr('y1', qubit1Y + 8)
        .attr('x2', x + 8)
        .attr('y2', qubit1Y - 8)
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
      g.append('line')
        .attr('x1', x - 8)
        .attr('y1', qubit2Y - 8)
        .attr('x2', x + 8)
        .attr('y2', qubit2Y + 8)
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
      g.append('line')
        .attr('x1', x - 8)
        .attr('y1', qubit2Y + 8)
        .attr('x2', x + 8)
        .attr('y2', qubit2Y - 8)
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
      g.append('line')
        .attr('x1', x)
        .attr('y1', qubit1Y)
        .attr('x2', x)
        .attr('y2', qubit2Y)
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
    }

    function drawRotationGate(g: d3.Selection<SVGGElement, unknown, null, undefined>, x: number, y: number, label: string, angle: number | undefined, gate: Gate) {
      g.attr('data-gate-type', gate.type.toLowerCase())
      g.append('rect')
        .attr('x', x - 20)
        .attr('y', y - 15)
        .attr('width', 40)
        .attr('height', 30)
        .attr('fill', getGateColor(gate.type.toLowerCase(), 'fill'))
        .attr('stroke', getGateColor(gate.type.toLowerCase(), 'stroke'))
        .attr('stroke-width', 2)
        .attr('rx', 4)
        .attr('class', 'gate-element')
      g.append('text')
        .attr('x', x)
        .attr('y', y + 2)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-family', 'monospace')
        .attr('font-size', '12px')
        .attr('font-weight', 'bold')
        .text(label)
      if (angle !== undefined) {
        g.append('text')
          .attr('x', x)
          .attr('y', y + 12)
          .attr('text-anchor', 'middle')
          .attr('fill', 'white')
          .attr('font-family', 'monospace')
          .attr('font-size', '8px')
          .text(`(${angle.toFixed(2)})`)
      }
    }

    function drawPhaseGate(g: d3.Selection<SVGGElement, unknown, null, undefined>, x: number, y: number, angle: number | undefined, gate: Gate) {
      g.attr('data-gate-type', 'p')
      g.append('rect')
        .attr('x', x - 20)
        .attr('y', y - 15)
        .attr('width', 40)
        .attr('height', 30)
        .attr('fill', getGateColor('p', 'fill'))
        .attr('stroke', getGateColor('p', 'stroke'))
        .attr('stroke-width', 2)
        .attr('rx', 4)
        .attr('class', 'gate-element')
      g.append('text')
        .attr('x', x)
        .attr('y', y + 2)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-family', 'monospace')
        .attr('font-size', '12px')
        .attr('font-weight', 'bold')
        .text('P')
      if (angle !== undefined) {
        g.append('text')
          .attr('x', x)
          .attr('y', y + 12)
          .attr('text-anchor', 'middle')
          .attr('fill', 'white')
          .attr('font-family', 'monospace')
          .attr('font-size', '8px')
          .text(`(${angle.toFixed(2)})`)
      }
    }

    function drawMeasurementGate(g: d3.Selection<SVGGElement, unknown, null, undefined>, x: number, y: number, gate: Gate) {
      g.attr('data-gate-type', 'measure')
      // Measurement box
      g.append('rect')
        .attr('x', x - 15)
        .attr('y', y - 15)
        .attr('width', 30)
        .attr('height', 30)
        .attr('fill', getGateColor('measure', 'fill'))
        .attr('stroke', getGateColor('measure', 'stroke'))
        .attr('stroke-width', 2)
        .attr('rx', 4)
        .attr('class', 'gate-element')
      // Draw meter arc using path (semicircle)
      g.append('path')
        .attr('d', `M ${x - 8} ${y + 5} A 8 8 0 0 1 ${x + 8} ${y + 5}`)
        .attr('fill', 'none')
        .attr('stroke', 'white')
        .attr('stroke-width', 2)
      // Draw meter needle
      g.append('line')
        .attr('x1', x)
        .attr('y1', y + 5)
        .attr('x2', x + 5)
        .attr('y2', y - 3)
        .attr('stroke', 'white')
        .attr('stroke-width', 2)
      // Add "M" label
      g.append('text')
        .attr('x', x)
        .attr('y', y - 6)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-family', 'monospace')
        .attr('font-size', '8px')
        .attr('font-weight', 'bold')
        .text('M')
    }

    function drawGenericGate(g: d3.Selection<SVGGElement, unknown, null, undefined>, x: number, y: number, label: string, gate: Gate) {
      g.attr('data-gate-type', gate.type.toLowerCase())
      g.append('rect')
        .attr('x', x - 15)
        .attr('y', y - 15)
        .attr('width', 30)
        .attr('height', 30)
        .attr('fill', colors.gateStroke)
        .attr('stroke', colors.gateStroke)
        .attr('stroke-width', 2)
        .attr('rx', 4)
        .attr('class', 'gate-element')
      g.append('text')
        .attr('x', x)
        .attr('y', y + 5)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-family', 'monospace')
        .attr('font-size', '10px')
        .attr('font-weight', 'bold')
        .text(label.length > 4 ? label.substring(0, 4) : label)
    }

    // Draw gates with interactivity
    gates.forEach((gate, gateIndex) => {
      // Use timestamp for x position if available, otherwise fall back to gate index
      const timeSlot = gate.timestamp ?? gateIndex
      const x = timeSlot * gateSpacing + 40
      const y = gate.qubit * qubitSpacing + 30
      
      // Create gate group for interactivity
      const gateGroup = mainGroup.append('g')
        .attr('class', 'gate-group')
        .attr('data-gate-index', gateIndex)
        .style('cursor', 'pointer')
        .on('mouseenter', function(event) {
          setHoveredGate(gate)
          d3.select(this).selectAll('rect, circle').attr('stroke-width', 3).attr('stroke', colors.hover)
          
          // Show tooltip
          const gateInfo = getGateInfo(gate)
          tooltip.transition().duration(200).style('opacity', 0.95)
          tooltip.html(gateInfo)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 10) + 'px')
        })
        .on('mouseleave', function() {
          setHoveredGate(null)
          if (selectedGate !== gate) {
            const element = d3.select(this).node() as SVGElement
            const gateType = element.getAttribute('data-gate-type') || ''
            const defaultStroke = getGateColor(gateType, 'stroke')
            d3.select(this).selectAll('rect, circle').attr('stroke-width', 2).attr('stroke', defaultStroke)
          }
          tooltip.transition().duration(200).style('opacity', 0)
        })
        .on('click', function() {
          const newSelected = selectedGate === gate ? null : gate
          setSelectedGate(newSelected)
          // Update all gates to show selection
          mainGroup.selectAll('.gate-group').each(function() {
            const element = d3.select(this).node() as SVGElement
            const gateIndex = parseInt(element.getAttribute('data-gate-index') || '0')
            const isSelected = gates[gateIndex] === newSelected
            const gateType = element.getAttribute('data-gate-type') || ''
            const defaultStroke = getGateColor(gateType, 'stroke')
            d3.select(this).selectAll('rect, circle')
              .attr('stroke-width', isSelected ? 3 : 2)
              .attr('stroke', isSelected ? colors.selected : defaultStroke)
          })
        })

      // Draw gate based on type
      switch (gate.type.toLowerCase()) {
        case 'h':
        case 'hadamard':
          drawHGate(gateGroup, x, y, gate.name || 'H', gate)
          break
        case 'x':
        case 'pauli-x':
          drawXGate(gateGroup, x, y, gate)
          break
        case 'y':
        case 'pauli-y':
          drawYGate(gateGroup, x, y, gate)
          break
        case 'z':
        case 'pauli-z':
          drawZGate(gateGroup, x, y, gate)
          break
        case 's':
          drawSGate(gateGroup, x, y, gate)
          break
        case 't':
          drawTGate(gateGroup, x, y, gate)
          break
        case 'cx':
        case 'cnot':
          if (gate.control !== undefined && gate.target !== undefined) {
            drawCNOTGate(gateGroup, x, gate.control * qubitSpacing + 30, gate.target * qubitSpacing + 30, gate)
          }
          break
        case 'cz':
          if (gate.control !== undefined && gate.target !== undefined) {
            drawCZGate(gateGroup, x, gate.control * qubitSpacing + 30, gate.target * qubitSpacing + 30, gate)
          }
          break
        case 'swap':
          if (gate.control !== undefined && gate.target !== undefined) {
            drawSWAPGate(gateGroup, x, gate.control * qubitSpacing + 30, gate.target * qubitSpacing + 30, gate)
          }
          break
        case 'rz':
        case 'ry':
        case 'rx':
          drawRotationGate(gateGroup, x, y, gate.type.toUpperCase(), gate.angle, gate)
          break
        case 'p':
        case 'phaseshift':
          drawPhaseGate(gateGroup, x, y, gate.angle, gate)
          break
        case 'measure':
        case 'measurement':
          drawMeasurementGate(gateGroup, x, y, gate)
          break
        default:
          drawGenericGate(gateGroup, x, y, gate.type.toUpperCase(), gate)
      }
    })

    // Cleanup tooltip on unmount
    return () => {
      tooltip.remove()
    }
  }, [gates, qubits, selectedGate, hoveredGate, isDarkMode, colors])

  useEffect(() => {
    const handleDownload = () => {
      if (!svgRef.current) return;
      
      const svgElement = svgRef.current;
      const serializer = new XMLSerializer();
      let svgString = serializer.serializeToString(svgElement);
      
      if (!svgString.match(/^<svg[^>]+xmlns="http\:\/\/www\.w3\.org\/2000\/svg"/)) {
        svgString = svgString.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
      }

      const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(svgBlob);
      
      const link = document.createElement('a');
      link.href = url;
      link.download = 'circuit-diagram.svg';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    };

    window.addEventListener('download-circuit-svg', handleDownload);
    return () => window.removeEventListener('download-circuit-svg', handleDownload);
  }, []);

  if (gates.length === 0) {
    return (
      <div className={`flex items-center justify-center h-32 border-2 border-dashed border-gray-600 rounded-lg ${className}`}>
        <p className="text-black dark:text-gray-400 text-sm">No circuit to visualize</p>
      </div>
    )
  }

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {selectedGate && (
        <div className="absolute top-2 right-2 bg-editor-bg border border-editor-border rounded-lg p-3 text-sm z-10 max-w-xs">
          <div className="font-bold mb-2 text-quantum-blue-light">Gate Details</div>
          <div className="space-y-1 text-editor-text">
            <div><strong>Type:</strong> {selectedGate.type.toUpperCase()}</div>
            {selectedGate.control !== undefined && selectedGate.target !== undefined ? (
              <>
                <div><strong>Control:</strong> q{selectedGate.control}</div>
                <div><strong>Target:</strong> q{selectedGate.target}</div>
              </>
            ) : (
              <div><strong>Qubit:</strong> q{selectedGate.qubit}</div>
            )}
            {selectedGate.angle !== undefined && (
              <div>
                <strong>Angle:</strong> {selectedGate.angle.toFixed(3)} rad ({((selectedGate.angle * 180) / Math.PI).toFixed(1)}°)
              </div>
            )}
          </div>
          <button
            onClick={() => setSelectedGate(null)}
            className="mt-2 text-xs text-black dark:text-gray-400 hover:text-white"
          >
            Close
          </button>
        </div>
      )}
      <div className="overflow-auto">
        <svg ref={svgRef} className="min-w-full"></svg>
      </div>
    </div>
  )
}
