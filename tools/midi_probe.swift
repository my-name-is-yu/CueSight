#!/usr/bin/env swift
import CoreMIDI
import Foundation

final class MidiProbe {
    var client = MIDIClientRef()
    var input = MIDIPortRef()

    func start() {
        MIDIClientCreate("Rokid MIDI Probe" as CFString, nil, nil, &client)
        MIDIInputPortCreateWithProtocol(
            client,
            "Rokid MIDI Input" as CFString,
            MIDIProtocolID._1_0,
            &input
        ) { eventList, context in
            let probe = Unmanaged<MidiProbe>.fromOpaque(context!).takeUnretainedValue()
            probe.handle(eventList: eventList.pointee)
        }

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

    func handle(eventList: MIDIEventList) {
        withUnsafePointer(to: eventList.packet) { packetPointer in
            var packet = packetPointer
            for _ in 0..<eventList.numPackets {
                let words = Mirror(reflecting: packet.pointee.words).children.compactMap { $0.value as? UInt32 }
                for word in words.prefix(Int(packet.pointee.wordCount)) {
                    emit(word: word)
                }
                packet = UnsafePointer(MIDIEventPacketNext(UnsafeMutablePointer(mutating: packet)))
            }
        }
    }

    func emit(word: UInt32) {
        let byte0 = UInt8(word & 0xFF)
        let byte1 = UInt8((word >> 8) & 0xFF)
        let byte2 = UInt8((word >> 16) & 0xFF)
        let byte3 = UInt8((word >> 24) & 0xFF)

        let status: UInt8
        let data1: UInt8
        let data2: UInt8
        if byte0 >> 4 == 0x2 {
            status = byte1
            data1 = byte2
            data2 = byte3
        } else {
            status = byte0
            data1 = byte1
            data2 = byte2
        }

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
