#!/usr/bin/env swift
import CoreMIDI
import Foundation

final class MidiProbe {
    var client = MIDIClientRef()
    var input = MIDIPortRef()

    func start() {
        MIDIClientCreate("Rokid MIDI Probe" as CFString, nil, nil, &client)
        MIDIInputPortCreate(
            client,
            "Rokid MIDI Input" as CFString,
            { packetList, context, _ in
                let probe = Unmanaged<MidiProbe>.fromOpaque(context!).takeUnretainedValue()
                probe.handle(packetList: packetList.pointee)
            },
            Unmanaged.passUnretained(self).toOpaque(),
            &input
        )

        let sourceCount = MIDIGetNumberOfSources()
        if sourceCount == 0 {
            fputs("No MIDI sources found\n", stderr)
        }
        fputs("MIDI sources: \(sourceCount)\n", stderr)
        for index in 0..<sourceCount {
            let source = MIDIGetSource(index)
            MIDIPortConnectSource(input, source, Unmanaged.passUnretained(self).toOpaque())
            print("{\"event\":\"source\",\"index\":\(index),\"name\":\"\(escape(name(of: source)))\"}")
            fputs("source \(index): \(name(of: source))\n", stderr)
            fflush(stdout)
        }
        let destinationCount = MIDIGetNumberOfDestinations()
        fputs("MIDI destinations: \(destinationCount)\n", stderr)
        for index in 0..<destinationCount {
            let destination = MIDIGetDestination(index)
            fputs("destination \(index): \(name(of: destination))\n", stderr)
        }
        RunLoop.current.run()
    }

    func handle(packetList: MIDIPacketList) {
        withUnsafePointer(to: packetList.packet) { packetPointer in
            var packet = packetPointer
            for _ in 0..<packetList.numPackets {
                let data = Mirror(reflecting: packet.pointee.data).children.compactMap { $0.value as? UInt8 }
                let bytes = Array(data.prefix(Int(packet.pointee.length)))
                var index = 0
                while index < bytes.count {
                    let status = bytes[index]
                    let kind = status & 0xF0
                    let length = (kind == 0xC0 || kind == 0xD0) ? 2 : 3
                    if index + length <= bytes.count {
                        emit(bytes: Array(bytes[index..<(index + length)]))
                    }
                    index += length
                }
                packet = UnsafePointer(MIDIPacketNext(UnsafeMutablePointer(mutating: packet)))
            }
        }
    }

    func emit(bytes: [UInt8]) {
        let status = bytes[0]
        let data1 = bytes.count > 1 ? bytes[1] : 0
        let data2 = bytes.count > 2 ? bytes[2] : 0
        let kind = status & 0xF0
        let channel = Int(status & 0x0F) + 1
        if kind == 0xB0 {
            print("{\"event\":\"cc\",\"channel\":\(channel),\"control\":\(Int(data1)),\"value\":\(Int(data2))}")
        } else if kind == 0x90 || kind == 0x80 {
            let event = kind == 0x90 && data2 > 0 ? "note_on" : "note_off"
            print("{\"event\":\"\(event)\",\"channel\":\(channel),\"note\":\(Int(data1)),\"velocity\":\(Int(data2))}")
        }
        fflush(stdout)
    }

    func name(of endpoint: MIDIEndpointRef) -> String {
        var unmanaged: Unmanaged<CFString>?
        MIDIObjectGetStringProperty(endpoint, kMIDIPropertyDisplayName, &unmanaged)
        return unmanaged?.takeRetainedValue() as String? ?? "Unknown"
    }

    func escape(_ value: String) -> String {
        value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
    }
}

MidiProbe().start()
