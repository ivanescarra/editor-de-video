// silueta: máscara de persona fotograma a fotograma con Apple Vision (VNGeneratePersonSegmentationRequest).
// Uso: silueta <video> <ancho> <alto>   → escribe en stdout fotogramas en gris de 8 bits (ancho×alto), uno por fotograma.
// Ejemplo: silueta in.mp4 960 540 | ffmpeg -f rawvideo -pix_fmt gray -s 960x540 -r 30000/1001 -i - mascara.mp4

import AVFoundation
import CoreImage
import Foundation
import Vision

let args = CommandLine.arguments
guard args.count >= 4, let W = Int(args[2]), let H = Int(args[3]) else {
    FileHandle.standardError.write("Uso: silueta <video> <ancho> <alto>\n".data(using: .utf8)!)
    exit(1)
}
let asset = AVURLAsset(url: URL(fileURLWithPath: args[1]))
let sem = DispatchSemaphore(value: 0)
var pista: AVAssetTrack?
Task { pista = try? await asset.loadTracks(withMediaType: .video).first; sem.signal() }
sem.wait()
guard let track = pista, let reader = try? AVAssetReader(asset: asset) else { exit(1) }
let out = AVAssetReaderTrackOutput(track: track, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
reader.add(out)
reader.startReading()

let ctx = CIContext()
let request = VNGeneratePersonSegmentationRequest()
request.qualityLevel = .accurate
request.outputPixelFormat = kCVPixelFormatType_OneComponent8
let gray = CGColorSpaceCreateDeviceGray()
var buffer = [UInt8](repeating: 0, count: W * H)
let stdout = FileHandle.standardOutput
var n = 0

while let sample = out.copyNextSampleBuffer(), let px = CMSampleBufferGetImageBuffer(sample) {
    let handler = VNImageRequestHandler(cvPixelBuffer: px, options: [:])
    var wrote = false
    if (try? handler.perform([request])) != nil, let mask = request.results?.first?.pixelBuffer {
        let ci = CIImage(cvPixelBuffer: mask)
        let sx = CGFloat(W) / ci.extent.width, sy = CGFloat(H) / ci.extent.height
        let scaled = ci.transformed(by: CGAffineTransform(scaleX: sx, y: sy))
        buffer.withUnsafeMutableBytes { ptr in
            ctx.render(scaled, toBitmap: ptr.baseAddress!, rowBytes: W, bounds: CGRect(x: 0, y: 0, width: W, height: H),
                       format: .L8, colorSpace: gray)
        }
        wrote = true
    }
    if !wrote { buffer = [UInt8](repeating: 0, count: W * H) }
    stdout.write(Data(buffer))
    n += 1
}
FileHandle.standardError.write("silueta: \(n) fotogramas\n".data(using: .utf8)!)
