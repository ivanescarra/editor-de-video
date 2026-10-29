// caras: localiza la cara en un vídeo con Apple Vision.
// Uso: caras <video> <salida.json> [muestras_por_segundo=5]
// Salida: {"ancho","alto","duracion","muestras":[{"t","x","y","w","h"}]}
// x, y, w, h normalizados 0-1 con origen arriba a la izquierda; sin cara → sin x.

import AVFoundation
import Foundation
import Vision

let args = CommandLine.arguments
guard args.count >= 3 else {
    FileHandle.standardError.write("Uso: caras <video> <salida.json> [muestras_por_segundo]\n".data(using: .utf8)!)
    exit(1)
}
let url = URL(fileURLWithPath: args[1])
let salida = URL(fileURLWithPath: args[2])
let porSegundo = args.count > 3 ? Double(args[3]) ?? 5 : 5

let asset = AVURLAsset(url: url)
let sem = DispatchSemaphore(value: 0)
var pista: AVAssetTrack?
var duracion = 0.0
Task {
    pista = try? await asset.loadTracks(withMediaType: .video).first
    duracion = (try? await asset.load(.duration).seconds) ?? 0
    sem.signal()
}
sem.wait()
guard let track = pista else { print("No hay pista de vídeo"); exit(1) }

let sem2 = DispatchSemaphore(value: 0)
var tamano = CGSize.zero
var transform = CGAffineTransform.identity
Task {
    tamano = (try? await track.load(.naturalSize)) ?? .zero
    transform = (try? await track.load(.preferredTransform)) ?? .identity
    sem2.signal()
}
sem2.wait()
let rect = CGRect(origin: .zero, size: tamano).applying(transform)
let ancho = Int(abs(rect.width)), alto = Int(abs(rect.height))

// Orientación según la rotación del vídeo grabado con el móvil
let angulo = atan2(transform.b, transform.a)
let orientacion: CGImagePropertyOrientation
switch Int((angulo * 180 / .pi).rounded()) {
case 90: orientacion = .right
case -90: orientacion = .left
case 180, -180: orientacion = .down
default: orientacion = .up
}

let reader = try AVAssetReader(asset: asset)
let out = AVAssetReaderTrackOutput(track: track, outputSettings: [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarFullRange
])
out.alwaysCopiesSampleData = false
reader.add(out)
reader.startReading()

var muestras: [[String: Double]] = []
var siguiente = 0.0
let paso = 1.0 / porSegundo
while let sample = out.copyNextSampleBuffer() {
    let t = CMSampleBufferGetPresentationTimeStamp(sample).seconds
    if t + 0.0001 < siguiente { continue }
    siguiente = t + paso
    guard let px = CMSampleBufferGetImageBuffer(sample) else { continue }
    let req = VNDetectFaceRectanglesRequest()
    let handler = VNImageRequestHandler(cvPixelBuffer: px, orientation: orientacion)
    try? handler.perform([req])
    // La cara más grande es la de quien habla
    if let cara = (req.results ?? []).max(by: { $0.boundingBox.width * $0.boundingBox.height < $1.boundingBox.width * $1.boundingBox.height }) {
        let b = cara.boundingBox
        muestras.append(["t": t, "x": b.minX, "y": 1 - b.maxY, "w": b.width, "h": b.height])
    } else {
        muestras.append(["t": t])
    }
}

let json: [String: Any] = ["ancho": ancho, "alto": alto, "duracion": duracion, "muestras": muestras]
let data = try JSONSerialization.data(withJSONObject: json, options: [.prettyPrinted])
try data.write(to: salida)
let conCara = muestras.filter { $0["x"] != nil }.count
print("Cara encontrada en \(conCara) de \(muestras.count) muestras")
